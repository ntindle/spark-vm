"""Single-source spark-vm version reader (docs/VERSIONING.md).

Every long-lived spark-vm component reports this version at startup so an
operator can tell which release is actually deployed. The VERSION file at the
repo root is the sole source of truth; deploy scripts install a copy next to
deployed standalone files (e.g. /home/swapd/VERSION), and this reader finds it
by walking up from the calling component's directory.

Never raises on read problems: a missing or unparseable VERSION yields
"0.0.0-unknown" so a bad version file can never break a component's startup.
Use sparkvm_version_strict() (or the --check flag) in tests and CI, where a
bad version should fail loudly.
"""

import os
import re
import sys

_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)

UNKNOWN = "0.0.0-unknown"


def find_version_file(start=None):
    """Walk up from `start` (default: this file's directory) to find VERSION.

    Returns the first VERSION file found, or None.
    """
    here = os.path.abspath(start or os.path.dirname(__file__))
    d = here if os.path.isdir(here) else os.path.dirname(here)
    for _ in range(8):
        cand = os.path.join(d, "VERSION")
        if os.path.isfile(cand):
            return cand
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def sparkvm_version(start=None):
    """Return the repo VERSION string, or "0.0.0-unknown" on any problem."""
    path = find_version_file(start)
    if path is None:
        return UNKNOWN
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read().strip()
    except OSError:
        return UNKNOWN
    return text if _SEMVER_RE.match(text) else UNKNOWN


def sparkvm_version_strict(start=None):
    """Like sparkvm_version(), but raise ValueError when VERSION is missing/invalid."""
    path = find_version_file(start)
    if path is None:
        raise ValueError("no VERSION file found walking up from %r" % (start,))
    with open(path, encoding="utf-8") as f:
        text = f.read().strip()
    if not _SEMVER_RE.match(text):
        raise ValueError("invalid semver in %s: %r" % (path, text))
    return text


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    check = "--check" in argv
    try:
        version = sparkvm_version_strict()
        print(version)
        return 0
    except ValueError as e:
        print("sparkvm_version: %s" % e, file=sys.stderr)
        print(UNKNOWN)
        return 1 if check else 0


if __name__ == "__main__":
    sys.exit(main())
