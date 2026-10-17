"""Pin tests for scripts/install.sh --update (issue #1611, F-PKG-6).

The tag-to-tag updater moves the agent checkout from its current release
tag to a newer one, in place. These tests pin its load-bearing properties
with REAL git fixtures (the behavior under test is git semantics — tag
resolution, detached checkout, ref shadowing — so stubbed git would prove
nothing).

Fixture: an "upstream" repo with two releases (v1.2.3, v1.2.4, each with
a matching VERSION file), and a "box" checkout cloned at v1.2.3 detached
at the tag commit — exactly what --version installs.

Tests pin:
1. Flag contracts — --update/--to parsing, grammar, --to needs --update,
   --update + --version conflicts.
2. Happy path — the checkout moves v1.2.3 -> v1.2.4 (detached, VERSION
   verified), and the identity gate refuses the wrong user.
3. Fail-closed edges — dirty tree, downgrade, non-versioned checkout,
   ambiguous tags, branch-shadowing-the-tag, unknown --to target all die
   loudly; same-version is an idempotent skip; --dry-run mutates nothing.
"""

import subprocess
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "install.sh"


def _update_fixture(tmp_path, from_tag="v1.2.3", to_tag="v1.2.4"):
    """Build upstream (two tagged releases) + a box checkout at from_tag.

    Returns (upstream, box). The box is detached at the from_tag commit with
    origin pointing at upstream — the shape --version leaves behind.
    """
    upstream = tmp_path / "upstream"
    box = tmp_path / "box"
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
    }

    def git(*args, cwd=None):
        proc = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            cwd=str(cwd or upstream),
            env={**__import__("os").environ, **env},
            timeout=60,
        )
        assert proc.returncode == 0, f"git {args}: {proc.stderr}"
        return proc.stdout.strip()

    upstream.mkdir(parents=True)
    git("init", "-q", str(upstream))
    (upstream / "VERSION").write_text(f"{from_tag[1:]}\n")
    git("-C", str(upstream), "add", "VERSION")
    git("-C", str(upstream), "commit", "-qm", "r1")
    git("-C", str(upstream), "tag", from_tag)
    (upstream / "VERSION").write_text(f"{to_tag[1:]}\n")
    git("-C", str(upstream), "add", "VERSION")
    git("-C", str(upstream), "commit", "-qm", "r2")
    git("-C", str(upstream), "tag", to_tag)
    git("clone", "-q", "--branch", from_tag, str(upstream), str(box))
    git("-C", str(box), "checkout", "-q", "--detach", from_tag)
    return upstream, box


def _source():
    return (
        "_src_out=$(mktemp); "
        f"source {SCRIPT} >\"$_src_out\" 2>&1; _src_rc=$?; "
        '_src_content=$(cat "$_src_out"); rm -f "$_src_out"; '
        '[ "$_src_rc" = 0 ] || { echo "source failed: $_src_content"; exit 9; }; '
        '[ -z "$_src_content" ] || { echo "sourcing printed: $_src_content"; exit 9; }; '
    )


def _run_bash(code):
    import os

    return subprocess.run(
        ["bash", "-c", code],
        capture_output=True,
        text=True,
        env=dict(os.environ),
        cwd=str(REPO),
        timeout=60,
    )


def test_update_flag_parsing_and_grammar():
    code = _source()
    code += textwrap.dedent(
        """\
        parse_args --update --to v1.2.4
        [ "$UPDATE" = 1 ] || { echo "--update not set"; exit 1; }
        [ "$UPDATE_TO" = v1.2.4 ] || { echo "--to space form failed: $UPDATE_TO"; exit 1; }
        parse_args --update --to=v2.0.0-rc.1
        [ "$UPDATE_TO" = v2.0.0-rc.1 ] || { echo "--to equals form failed"; exit 1; }
        for bad in main v1.2 'v1.2.3;rm -rf /' --upload-pack=x; do
          if ( parse_args --update --to "$bad" ) 2>/dev/null; then echo "accepted bad --to: $bad"; exit 1; fi
        done
        # --to without --update dies (parse_args never resets globals between
        # calls, so UPDATE is zeroed here to make the probe honest)
        UPDATE=0
        if ( parse_args --to v1.2.4 ) 2>/dev/null; then echo "--to without --update accepted"; exit 1; fi
        # --update with --version dies (the pin belongs to installs)
        UPDATE=0; INSTALL_VERSION=
        if ( parse_args --update --version v1.2.3 ) 2>/dev/null; then echo "--update --version accepted"; exit 1; fi
        # env-provided UPDATE_TO is validated too (the bootstrap re-exec passes flags by env)
        UPDATE_TO=main
        if ( parse_args --update ) 2>/dev/null; then echo "env bad --to accepted"; exit 1; fi
        UPDATE_TO=
        parse_args --update || { echo "--update rejected"; exit 1; }
        echo OK
        """
    )
    proc = _run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_update_moves_checkout_between_tags(tmp_path):
    _upstream, box = _update_fixture(tmp_path)
    who = subprocess.run(["id", "-un"], capture_output=True, text=True).stdout.strip()
    code = _source()
    code += textwrap.dedent(
        f"""\
        AGENT_USER={who}; AGENT_REPO="{box}"; UPDATE=1; UPDATE_TO=v1.2.4; DRY_RUN=0
        out=$(run_update 2>&1); rc=$?
        [ $rc = 0 ] || {{ echo "update failed: $out"; exit 1; }}
        echo "$out" | grep -q "updating .* from release v1.2.3 to v1.2.4" || {{ echo "no move note: $out"; exit 1; }}
        [ "$(cat "{box}/VERSION")" = "1.2.4" ] || {{ echo "VERSION not moved"; exit 1; }}
        [ "$(git -C "{box}" describe --tags --exact-match 2>/dev/null)" = "v1.2.4" ] || {{ echo "not at tag commit"; exit 1; }}
        echo OK
        """
    )
    proc = _run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_update_identity_gate_refuses_wrong_user(tmp_path):
    _upstream, box = _update_fixture(tmp_path)
    code = _source()
    code += textwrap.dedent(
        f"""\
        AGENT_USER=definitely-not-a-real-user; AGENT_REPO="{box}"; UPDATE=1; UPDATE_TO=v1.2.4
        if ( run_update ) 2>/dev/null; then echo "wrong user accepted"; exit 1; fi
        echo OK
        """
    )
    proc = _run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_update_refuses_dirty_tree(tmp_path):
    # Honest fixture: the dirt must NOT break the VERSION pin — otherwise
    # current_release_tag's assertion dies before the dirty check is ever
    # reached and the test is vacuous. An untracked file dirties the tree
    # while the release pin holds, so this pins the dirty check itself.
    _upstream, box = _update_fixture(tmp_path)
    (box / "UNTRACKED").write_text("x\n")
    who = subprocess.run(["id", "-un"], capture_output=True, text=True).stdout.strip()
    code = _source()
    code += textwrap.dedent(
        f"""\
        AGENT_USER={who}; AGENT_REPO="{box}"; UPDATE=1; UPDATE_TO=v1.2.4; DRY_RUN=0
        rc=0; out=$(run_update 2>&1) || rc=$?
        [ $rc != 0 ] || {{ echo "dirty checkout accepted"; exit 1; }}
        echo "$out" | grep -q "local changes" || {{ echo "wrong refusal: $out"; exit 1; }}
        [ "$(cat "{box}/VERSION")" = "1.2.3" ] || {{ echo "checkout moved on refused update"; exit 1; }}
        echo OK
        """
    )
    proc = _run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_update_refuses_ambiguous_tags(tmp_path):
    # Two release-grammar tags point at HEAD: the updater must not guess
    # which release the box runs.
    _upstream, box = _update_fixture(tmp_path)
    who = subprocess.run(["id", "-un"], capture_output=True, text=True).stdout.strip()
    subprocess.run(
        ["git", "-C", str(box), "tag", "v1.2.3-alias"], check=True, timeout=60
    )
    code = _source()
    code += textwrap.dedent(
        f"""\
        AGENT_USER={who}; AGENT_REPO="{box}"; UPDATE=1; UPDATE_TO=v1.2.4; DRY_RUN=0
        rc=0; out=$(run_update 2>&1) || rc=$?
        [ $rc != 0 ] || {{ echo "ambiguous release accepted"; exit 1; }}
        echo "$out" | grep -q "ambiguous release" || {{ echo "wrong refusal: $out"; exit 1; }}
        [ "$(cat "{box}/VERSION")" = "1.2.3" ] || {{ echo "checkout moved on refused update"; exit 1; }}
        echo OK
        """
    )
    proc = _run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_update_refuses_shadowed_branch(tmp_path):
    # A branch shadowing the release tag: `git checkout --detach <tag>`
    # resolves the branch first (unlike rev-parse, which prefers refs/tags),
    # so the checkout lands on the branch tip — and the landed==want_commit
    # guard must refuse loudly instead of installing the branch as the
    # release. This pins the guard itself.
    _upstream, box = _update_fixture(tmp_path)
    who = subprocess.run(["id", "-un"], capture_output=True, text=True).stdout.strip()
    subprocess.run(
        ["git", "-C", str(box), "branch", "v1.2.4", "v1.2.3^{commit}"],
        check=True,
        timeout=60,
    )
    code = _source()
    code += textwrap.dedent(
        f"""\
        AGENT_USER={who}; AGENT_REPO="{box}"; UPDATE=1; UPDATE_TO=v1.2.4; DRY_RUN=0
        rc=0; out=$(run_update 2>&1) || rc=$?
        [ $rc != 0 ] || {{ echo "shadowed tag accepted"; exit 1; }}
        echo "$out" | grep -q "shadowing the release tag" || {{ echo "wrong refusal: $out"; exit 1; }}
        [ "$(cat "{box}/VERSION")" = "1.2.3" ] || {{ echo "release moved on refused update"; exit 1; }}
        echo OK
        """
    )
    proc = _run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_update_refuses_downgrade(tmp_path):
    upstream, box = _update_fixture(tmp_path)
    who = subprocess.run(["id", "-un"], capture_output=True, text=True).stdout.strip()
    # move box to v1.2.4 first (real git), then try to go back
    subprocess.run(
        ["git", "-C", str(box), "checkout", "-q", "--detach", "v1.2.4"],
        check=True,
        timeout=60,
    )
    code = _source()
    code += textwrap.dedent(
        f"""\
        AGENT_USER={who}; AGENT_REPO="{box}"; UPDATE=1; UPDATE_TO=v1.2.3; DRY_RUN=0
        if ( run_update ) 2>/dev/null; then echo "downgrade accepted"; exit 1; fi
        [ "$(cat "{box}/VERSION")" = "1.2.4" ] || {{ echo "checkout moved on refused downgrade"; exit 1; }}
        echo OK
        """
    )
    proc = _run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_update_same_version_is_idempotent_skip(tmp_path):
    _upstream, box = _update_fixture(tmp_path)
    who = subprocess.run(["id", "-un"], capture_output=True, text=True).stdout.strip()
    code = _source()
    code += textwrap.dedent(
        f"""\
        AGENT_USER={who}; AGENT_REPO="{box}"; UPDATE=1; UPDATE_TO=v1.2.3; DRY_RUN=0
        out=$(run_update 2>&1); rc=$?
        [ $rc = 0 ] || {{ echo "skip failed: $out"; exit 1; }}
        echo "$out" | grep -q "already at release v1.2.3" || {{ echo "no skip note: $out"; exit 1; }}
        echo OK
        """
    )
    proc = _run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_update_refuses_non_versioned_checkout(tmp_path):
    upstream, box = _update_fixture(tmp_path)
    who = subprocess.run(["id", "-un"], capture_output=True, text=True).stdout.strip()
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    # a non-tag commit on top: HEAD is not at a release
    (upstream / "VERSION").write_text("9.9.9\n")
    import os

    merged = dict(os.environ, **env)
    subprocess.run(
        ["git", "-C", str(box), "checkout", "-q", "--detach", "v1.2.4"], check=True, timeout=60
    )
    (box / "VERSION").write_text("9.9.9\n")
    subprocess.run(
        ["git", "-C", str(box), "add", "VERSION"], check=True, env=merged, timeout=60
    )
    subprocess.run(
        ["git", "-C", str(box), "commit", "-qm", "local"], check=True, env=merged, timeout=60
    )
    code = _source()
    code += textwrap.dedent(
        f"""\
        AGENT_USER={who}; AGENT_REPO="{box}"; UPDATE=1; UPDATE_TO=v1.2.4; DRY_RUN=0
        if ( run_update ) 2>/dev/null; then echo "non-versioned checkout accepted"; exit 1; fi
        echo OK
        """
    )
    proc = _run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_update_dry_run_mutates_nothing(tmp_path):
    _upstream, box = _update_fixture(tmp_path)
    who = subprocess.run(["id", "-un"], capture_output=True, text=True).stdout.strip()
    code = _source()
    code += textwrap.dedent(
        f"""\
        AGENT_USER={who}; AGENT_REPO="{box}"; UPDATE=1; UPDATE_TO=v1.2.4; DRY_RUN=1
        out=$(run_update 2>&1); rc=$?
        [ $rc = 0 ] || {{ echo "dry-run failed: $out"; exit 1; }}
        echo "$out" | grep -q "would fetch tags" || {{ echo "no fetch in plan: $out"; exit 1; }}
        [ "$(cat "{box}/VERSION")" = "1.2.3" ] || {{ echo "dry-run mutated the checkout"; exit 1; }}
        echo OK
        """
    )
    proc = _run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_update_default_target_is_latest_tag(tmp_path):
    _upstream, box = _update_fixture(tmp_path)
    who = subprocess.run(["id", "-un"], capture_output=True, text=True).stdout.strip()
    code = _source()
    code += textwrap.dedent(
        f"""\
        AGENT_USER={who}; AGENT_REPO="{box}"; UPDATE=1; UPDATE_TO=; DRY_RUN=0
        out=$(run_update 2>&1); rc=$?
        [ $rc = 0 ] || {{ echo "update failed: $out"; exit 1; }}
        echo "$out" | grep -q "to v1.2.4" || {{ echo "did not pick latest: $out"; exit 1; }}
        [ "$(cat "{box}/VERSION")" = "1.2.4" ] || {{ echo "checkout not moved"; exit 1; }}
        echo OK
        """
    )
    proc = _run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_update_unknown_target_dies_loud(tmp_path):
    _upstream, box = _update_fixture(tmp_path)
    who = subprocess.run(["id", "-un"], capture_output=True, text=True).stdout.strip()
    code = _source()
    code += textwrap.dedent(
        f"""\
        AGENT_USER={who}; AGENT_REPO="{box}"; UPDATE=1; UPDATE_TO=v9.9.9; DRY_RUN=0
        if ( run_update ) 2>/dev/null; then echo "unknown tag accepted"; exit 1; fi
        [ "$(cat "{box}/VERSION")" = "1.2.3" ] || {{ echo "checkout moved on refused target"; exit 1; }}
        echo OK
        """
    )
    proc = _run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_tag_grammar_rejects_smuggled_whitespace():
    # A pasted tag carrying a trailing newline must not validate: the =~
    # grammar's character class admits no whitespace (verified — bash's $
    # anchor does not match before a trailing newline, so the grammar
    # itself is the rejecting layer). ($() strips trailing newlines, so
    # the newline is appended via $'\n'.)
    code = _source()
    code += textwrap.dedent(
        """\
        nl_to="v1.2.4"; nl_to+=$'\n'
        if ( parse_args --update --to "$nl_to" ) 2>/dev/null; then echo "newline --to accepted"; exit 1; fi
        nl_ver="v1.2.3"; nl_ver+=$'\n'
        if ( parse_args --version "$nl_ver" ) 2>/dev/null; then echo "newline --version accepted"; exit 1; fi
        if ( UPDATE_TO="$nl_to" parse_args --update ) 2>/dev/null; then echo "env newline accepted"; exit 1; fi
        echo OK
        """
    )
    proc = _run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_redact_url_strips_userinfo_for_display():
    code = _source()
    code += textwrap.dedent(
        """\
        [ "$(redact_url 'https://user:pass@host/x.git')" = 'https://<redacted>@host/x.git' ] || { echo "creds not stripped"; exit 1; }
        [ "$(redact_url 'https://github.com/ntindle/spark-vm.git')" = 'https://github.com/ntindle/spark-vm.git' ] || { echo "plain url mangled"; exit 1; }
        [ "$(redact_url 'git@github.com:ntindle/spark-vm.git')" = 'git@github.com:ntindle/spark-vm.git' ] || { echo "scp url mangled"; exit 1; }
        echo OK
        """
    )
    proc = _run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")
