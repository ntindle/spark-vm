#!/usr/bin/env python3
"""Pin scripts/ci_shellcheck_files.py's selection against the pinned
action-shellcheck contract.

The helper is the single source of truth for "which shell files does CI
lint" — consumed by scripts/local-gate.sh step 5 and by
test_local_gate.py's repo-wide shellcheck pin — and its docstring claims
to replicate the pinned action's find expressions. Until this file, the
claim had zero direct test coverage: a pattern-list edit, a shebang-regex
tweak, or a silent SHA bump in ci.yml could all drift the local selection
away from what CI actually lints without any test noticing. (Verified
2026-10-19: the helper's output on the real repo is identical to the
action's literal find expressions — 40/40 files, zero divergence — so
these pins lock in a true statement, not a guess.)

Every assertion here is written against the ACTION's contract (verbatim
from ludeeus/action-shellcheck@00b27aa7cb85167568cb48a3838b75f4265f2bca),
hardcoded in this file — never against the helper's own constants — so a
helper edit that weakens selection fails loudly instead of moving the
goalposts with it.

Non-vacuity (each verified by neutering a scratch copy of the helper,
never the worktree — every neuter below fails its named test; some also
fail others, which is expected where fixtures share the `*.sh` pattern
and is not enumerated exhaustively):
- drop "*.sh" from the helper's pattern tuple ->
  test_pass1_name_patterns_match_action fails (verified: four more fail
  too — test_excludes, test_main_nul_delimited_contract,
  test_symlinks_never_selected, test_pass2_requires_dotless_and_executable
  — all pin `*.sh` fixtures)
- widen the shebang class to [abkz] -> the zsh mirror-gap test fails
- flip one hex digit in the helper docstring's SHA -> the SHA pin fails
- replace the end-anchored `.go` exclude with a substring check
  (".go" in rel) -> test_excludes fails (foo.go/run.sh wrongly dropped);
  honesty note: DELETING the exclude fails nothing — no selectable file
  can end in .go (no pass-1 pattern matches it, pass 2 requires dotless)
  — so the exclude is textual-parity-only, pinned by review, not by
  behavior
- break the pass-2 exec-bit gate -> test_pass2_requires_dotless_and_executable
  fails (also test_pass1_name_patterns_match_action — its non-executable
  Makefile negative control with `#!/bin/sh` would then select)
"""

import io
import os
import re
import stat
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from ci_shellcheck_files import ci_shellcheck_files, main
_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parent
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"
HELPER_SRC = _HERE / "ci_shellcheck_files.py"

# The action's -name list, verbatim from
# ludeeus/action-shellcheck@00b27aa7cb85167568cb48a3838b75f4265f2bca
# (the "Run the check" step's first find). Deliberately NOT imported from
# the helper — this list is the external truth the helper is pinned to.
_ACTION_NAME_PATTERNS = (
    "*.bash", ".bashrc", "bashrc", ".bash_aliases", ".bash_completion",
    ".bash_login", ".bash_logout", ".bash_profile", "bash_profile",
    "*.ksh", "suid_profile", "*.zsh", ".zlogin", "zlogin", ".zlogout",
    "zlogout", ".zprofile", "zprofile", ".zsenv", "zsenv", ".zshrc",
    "zshrc", "*.sh", "*.shlib",
)
# The action's shebang regex, verbatim: ^#! */[^ ]*/(env *)?[abk]*sh.
_ACTION_SHEBANG_RE = re.compile(r"^#![ ]*/[^ ]*/(env[ ]*)?[abk]*sh")


def _write(root, rel, content="", executable=False):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content.encode() if isinstance(content, str) else content)
    if executable:
        p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return p


def _pattern_probe(pattern):
    """A filename that exercises one action -name pattern."""
    if pattern.startswith("*"):
        return "probe" + pattern[1:]
    return pattern


def test_action_sha_docstring_matches_ci_yml():
    """The SHA the helper docstring claims to replicate is the SHA ci.yml
    actually pins — the docstring's "keep in sync if the SHA moves" is
    otherwise prose-only, and a bumped pin with a stale docstring would
    leave readers (and this suite) validating the wrong contract."""
    doc = HELPER_SRC.read_text()
    m = re.search(r"action-shellcheck@([0-9a-f]{40})", doc)
    assert m, "helper docstring names no action-shellcheck SHA"
    doc_sha = m.group(1)
    yml = CI_YML.read_text()
    m = re.search(r"action-shellcheck@([0-9a-f]{40})", yml)
    assert m, "ci.yml pins no action-shellcheck SHA"
    assert doc_sha == m.group(1), (
        "helper docstring SHA %s != ci.yml pinned SHA %s — re-read the "
        "action's find expressions at the new SHA" % (doc_sha, m.group(1))
    )


def test_pass1_name_patterns_match_action(tmp_path):
    """Every action -name pattern selects a file, and non-shell names do
    not — the pass-1 list can neither shrink nor broaden silently."""
    for pattern in _ACTION_NAME_PATTERNS:
        _write(tmp_path, _pattern_probe(pattern), "#!/bin/sh\n")
    _write(tmp_path, "README.md", "docs\n")
    _write(tmp_path, "foo.txt", "#!/bin/sh\n")
    _write(tmp_path, "Makefile", "#!/bin/sh\n")
    selected = {Path(p).name for p in ci_shellcheck_files(tmp_path)}
    for pattern in _ACTION_NAME_PATTERNS:
        assert _pattern_probe(pattern) in selected, (
            "action pattern %r selects nothing" % pattern
        )
    assert "README.md" not in selected
    assert "foo.txt" not in selected
    assert "Makefile" not in selected


def test_pass1_profile_path_patterns(tmp_path):
    """The action's -o -path '*/.profile' / '*/profile' alternatives:
    bare `profile` and `.profile` select anywhere; near-misses don't."""
    _write(tmp_path, "profile", "export X=1\n")
    _write(tmp_path, ".profile", "export X=1\n")
    _write(tmp_path, "sub/dir/profile", "export X=1\n")
    _write(tmp_path, "myprofile", "export X=1\n")
    _write(tmp_path, "xprofile", "export X=1\n")
    _write(tmp_path, "profile.bak", "export X=1\n")
    selected = {Path(p).name for p in ci_shellcheck_files(tmp_path)}
    assert "profile" in selected
    assert ".profile" in selected
    # sub/dir/profile's basename is "profile" — also in the set; the
    # negative assertions below are what prove the suffix logic.
    assert "myprofile" not in selected
    assert "xprofile" not in selected
    assert "profile.bak" not in selected
    # The nested profile really was visited (not silently skipped):
    assert str(tmp_path / "sub" / "dir" / "profile") in ci_shellcheck_files(
        tmp_path
    )


def test_pass2_shebang_selection(tmp_path):
    """Extension-less executables: sh-family shebangs select; everything
    else doesn't. Drives the action's ^#! */[^ ]*/(env *)?[abk]*sh."""
    cases = {
        "run_sh": ("#!/bin/sh\n", True),
        "run_bash": ("#!/bin/bash\n", True),
        "run_env_bash": ("#!/usr/bin/env bash\n", True),
        "run_env_sh": ("#!/usr/bin/env sh\n", True),
        "run_ksh": ("#!/bin/ksh\n", True),
        "run_ash": ("#!/bin/ash\n", True),
        "run_spaced": ("#!  /bin/sh\n", True),
        # NOTE: the action's shebang class is [abk]*sh — a zsh shebang on
        # an extension-less file is NOT matched by the action, and the
        # helper mirrors that (parity, not a fix; .zsh-suffixed files are
        # still caught by pass 1). Pinned so a "fix" that diverges from
        # the action fails loudly.
        "run_zsh": ("#!/bin/zsh\n", False),
        "run_python": ("#!/usr/bin/env python3\n", False),
        "run_fish": ("#!/usr/bin/fish\n", False),
        "run_none": ("echo just text\n", False),
        "run_empty": ("", False),
    }
    for name, (content, _) in cases.items():
        _write(tmp_path, name, content, executable=True)
    selected = {Path(p).name for p in ci_shellcheck_files(tmp_path)}
    for name, (_, want) in cases.items():
        assert (name in selected) == want, (
            "%r: expected selected=%s" % (name, want)
        )


def test_pass2_requires_dotless_and_executable(tmp_path):
    """Pass 2 needs BOTH extension-less AND any exec bit; pass 1 needs
    neither (name match alone selects)."""
    _write(tmp_path, "dotted.txt", "#!/bin/sh\n", executable=True)
    _write(tmp_path, "noexec", "#!/bin/sh\n", executable=False)
    _write(tmp_path, "plain.sh", "no shebang at all\n", executable=False)
    _write(tmp_path, "exec_noshebang", "echo hi\n", executable=True)
    selected = {Path(p).name for p in ci_shellcheck_files(tmp_path)}
    assert "dotted.txt" not in selected  # has a dot -> pass 2 ineligible
    assert "noexec" not in selected  # no exec bit -> pass 2 ineligible
    assert "plain.sh" in selected  # pass 1: name match, shebang/exec irrelevant
    assert "exec_noshebang" not in selected  # no shebang -> neither pass


def test_excludes(tmp_path):
    """.git contents and mvnw are excluded even when they'd otherwise
    select (mirrors the action's -path excludes). The *.go exclude is
    end-anchored, exactly like the action's `-path *.go` — a shell file
    UNDER a .go directory is still selected; a substring-style check
    (".go" in rel) would wrongly drop it, and this pin catches that.
    (Honesty note: a file literally ending in .go can never be selected
    by either the action or the helper — no pass-1 pattern matches it
    and pass 2 requires dotless — so the exclude is inert for endings;
    the live contract is that it must not overreach.)"""
    _write(tmp_path, ".git/hooks/pre-commit", "#!/bin/sh\n", executable=True)
    _write(tmp_path, "mvnw", "#!/bin/sh\n", executable=True)
    _write(tmp_path, "sub/mvnw", "#!/bin/sh\n", executable=True)
    _write(tmp_path, "foo.go/run.sh", "#!/bin/sh\n")
    _write(tmp_path, "x.git/kept.sh", "#!/bin/sh\n")  # not a .git dir
    selected = {Path(p).name for p in ci_shellcheck_files(tmp_path)}
    assert "pre-commit" not in selected
    assert "mvnw" not in selected
    assert "run.sh" in selected  # foo.go/ is not a .go file
    assert "kept.sh" in selected  # x.git is not .git


def test_symlinks_never_selected(tmp_path):
    """find's default -P never matches symlinks with -type f; the helper
    gates both passes identically."""
    _write(tmp_path, "target.sh", "#!/bin/sh\n")
    _write(tmp_path, "runtarget", "#!/bin/sh\n", executable=True)
    os.symlink(tmp_path / "target.sh", tmp_path / "link.sh")
    os.symlink(tmp_path / "runtarget", tmp_path / "linkrun")
    selected = {Path(p).name for p in ci_shellcheck_files(tmp_path)}
    assert "target.sh" in selected
    assert "runtarget" in selected
    assert "link.sh" not in selected
    assert "linkrun" not in selected


def test_non_utf8_first_line_still_selected(tmp_path):
    """The action greps raw bytes; a non-UTF-8 byte after the shebang must
    not drop the file (helper decodes ascii/replace, regex still matches
    the prefix)."""
    _write(tmp_path, "binish", b"#!/bin/sh \xff\xfe binary tail\n", executable=True)
    selected = {Path(p).name for p in ci_shellcheck_files(tmp_path)}
    assert "binish" in selected


def test_name_case_sensitivity(tmp_path):
    """find's -name is case-sensitive (fnmatch, not -iname); the helper
    uses fnmatchcase to match. PROBE.SH must not select."""
    _write(tmp_path, "PROBE.SH", "#!/bin/sh\n")
    selected = {Path(p).name for p in ci_shellcheck_files(tmp_path)}
    assert "PROBE.SH" not in selected


def test_unreadable_file_skipped(tmp_path):
    """An unreadable dotless executable takes the helper's `except
    OSError: continue` branch (the action's `head | grep` silently skips
    it the same way). Cannot occur in CI checkouts; skipped where the
    chmod is ineffective (root reads through permission bits)."""
    if os.geteuid() == 0:
        pytest.skip("chmod 000 is ineffective as root")
    p = _write(tmp_path, "locked", "#!/bin/sh\n", executable=True)
    p.chmod(0)
    try:
        selected = {Path(f).name for f in ci_shellcheck_files(tmp_path)}
    finally:
        p.chmod(0o755)
    assert "locked" not in selected


def test_main_empty_selection_emits_nothing(tmp_path, capsys):
    """The `if files:` guard: with nothing selected, main() prints
    nothing (no trailing NUL) and returns 0 — the xargs -r contract."""
    rc = main(["ci_shellcheck_files.py", str(tmp_path)])
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_main_nul_delimited_contract(tmp_path):
    """main() emits NUL-delimited absolute paths (the local-gate.sh
    xargs -0 contract): filenames with spaces survive as single entries,
    and the stream ends with a trailing NUL."""
    _write(tmp_path, "with space.sh", "#!/bin/sh\n")
    _write(tmp_path, "plain.sh", "#!/bin/sh\n")
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(["ci_shellcheck_files.py", str(tmp_path)])
    assert rc == 0
    out = buf.getvalue()
    assert out.endswith("\0"), "NUL-delimited stream must end with a NUL"
    entries = out[:-1].split("\0")
    assert str(tmp_path / "with space.sh") in entries
    assert str(tmp_path / "plain.sh") in entries
    assert len(entries) == 2, "space-containing filename split: %r" % entries


def test_selection_sorted_absolute_no_dupes(tmp_path):
    """Selection is sorted, repo-root-absolute, and duplicate-free (the
    action can list a file twice when both finds match; the helper's
    contract is one entry per file)."""
    _write(tmp_path, "b.sh", "#!/bin/sh\n")
    _write(tmp_path, "a.sh", "#!/bin/sh\n")
    _write(tmp_path, "profile", "#!/bin/sh\n", executable=True)
    files = ci_shellcheck_files(tmp_path)
    assert files == sorted(files)
    assert len(files) == len(set(files))
    assert all(os.path.isabs(f) for f in files)


def test_real_repo_every_selection_justified():
    """On the real repo, every file the helper selects is justified by the
    ACTION's contract, re-derived here independently: a pass-1 name/path
    match, or a dotless executable whose first line matches the action's
    shebang regex. Catches accidental broadening on the tree CI lints."""
    import fnmatch

    def pass1(name, rel):
        if ("/" + rel).endswith(("/.profile", "/profile")):
            return True
        return any(fnmatch.fnmatchcase(name, pat) for pat in _ACTION_NAME_PATTERNS)

    files = ci_shellcheck_files(REPO_ROOT)
    assert files, "helper selected nothing on the real repo — contract broken"
    unjustified = []
    for f in files:
        p = Path(f)
        rel = p.relative_to(REPO_ROOT).as_posix()
        if pass1(p.name, rel):
            continue
        if "." in p.name or not (p.stat().st_mode & 0o111):
            unjustified.append((f, "not pass-1 and not dotless-executable"))
            continue
        first = p.open("rb").readline().decode("ascii", "replace")
        if not _ACTION_SHEBANG_RE.match(first):
            unjustified.append((f, "pass-2 candidate but shebang unmatched"))
    assert not unjustified, "selections the action would not make: %r" % (
        unjustified,
    )
