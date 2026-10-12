"""The standalone shellcheck CI job's file selection, as a shared helper.

Single source of truth for "which shell files does CI lint": both
`scripts/local-gate.sh` step 5 and the suite's repo-wide pin
(`scripts/test_local_gate.py::test_repo_shell_scripts_pass_shellcheck_error`)
consume this module, so a selection change lands in one place.

Selection replicates the pinned action
(ludeeus/action-shellcheck@00b27aa7cb85167568cb48a3838b75f4265f2bca —
the SHA pinned in .github/workflows/ci.yml):

Pass 1 — named shell files: the basename matches the action's -name
list (*.sh, *.bash, *.ksh, *.zsh, *.shlib, .bashrc, ...), shebang or not.
Pass 2 — extension-less executables: no '.' in the basename, any exec
bit set (find -perm /111), whose FIRST line matches the action's
shebang regex ^#! */[^ ]*/(env *)?[abk]*sh.

Excludes (mirroring the action): .git, *.go, */mvnw. Keep this helper in
sync with the pinned action version — if the SHA moves, re-read the
action's find expression and update both passes.
"""
import fnmatch
import re
import sys
from pathlib import Path

# The action's -name list, verbatim.
_ACTION_SHELL_NAME_PATTERNS = (
    "*.bash", ".bashrc", "bashrc", ".bash_aliases", ".bash_completion",
    ".bash_login", ".bash_logout", ".bash_profile", "bash_profile",
    "*.ksh", "suid_profile", "*.zsh", ".zlogin", "zlogin", ".zlogout",
    "zlogout", ".zprofile", "zprofile", ".zsenv", "zsenv", ".zshrc",
    "zshrc", "*.sh", "*.shlib",
)
# The action's -path patterns '*/.profile' and '*/profile', evaluated
# against '/'-prefixed relative paths the way find sees './profile'.
_ACTION_PROFILE_PATH_SUFFIXES = ("/.profile", "/profile")
_ACTION_SHEBANG_RE = re.compile(r"^#![ ]*/[^ ]*/(env[ ]*)?[abk]*sh")


def ci_shellcheck_files(root):
    """Return the sorted list of repo-root-absolute shell-file paths the
    standalone shellcheck CI job would lint under `root`."""
    root = Path(root)
    files = []
    for p in root.rglob("*"):
        # Both of the action's finds carry `-type f`, and under find's
        # default -P that never matches symlinks or directories — gate both
        # passes identically (a symlinked *.sh is selected by neither CI
        # nor this helper).
        if p.is_symlink() or not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if "/.git/" in f"/{rel}":
            continue
        if rel.endswith(".go") or rel == "mvnw" or rel.endswith("/mvnw"):
            continue  # the action's -path excludes, mirrored for parity
        name = p.name
        if ("/" + rel).endswith(_ACTION_PROFILE_PATH_SUFFIXES) or any(
            fnmatch.fnmatchcase(name, pat) for pat in _ACTION_SHELL_NAME_PATTERNS
        ):
            files.append(p)  # pass 1: named shell file, shebang or not
            continue
        if "." in name or not (p.stat().st_mode & 0o111):
            continue  # pass 2 needs an extension-less executable
        try:
            # First line only, like the action's `head -n1`.
            with p.open("rb") as fh:
                first = fh.readline().decode("ascii", "replace")
        except OSError:
            continue  # CI's -exec head|grep silently skips unreadable files
        if _ACTION_SHEBANG_RE.match(first):
            files.append(p)
    return sorted(str(p) for p in files)


def main(argv):
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent.parent
    files = ci_shellcheck_files(root)
    # NUL-delimited: filenames with spaces/newlines survive as single
    # arguments into `xargs -0`.
    if files:
        sys.stdout.write("\0".join(files) + "\0")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
