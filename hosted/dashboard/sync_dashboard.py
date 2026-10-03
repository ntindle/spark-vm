#!/usr/bin/env python3
"""Re-inline the fleet dashboard into the control-plane worker.py.

The canonical copy of the fleet dashboard is `dashboard.html` (this
directory). The control-plane Worker deploys as a single file, so it
carries the page inline between the BEGIN/END marker comments, and
`test_dashboard.py` asserts the inlined copy is byte-identical to the
canonical one.

Re-inlining by hand (copy-paste) is how the copies drift. Run this
instead::

    ./sync_dashboard.py                          # default worker checkout
    SPARKVM_WORKER_PATH=/path/to/worker.py ./sync_dashboard.py
    ./sync_dashboard.py --worker /path/to/worker.py
    ./sync_dashboard.py --check                  # verify only, no write

The worker-path resolution is shared with the test module: the
``SPARKVM_WORKER_PATH`` environment variable overrides the default
(the loop VM's control-plane checkout).

Stdlib only — no pytest needed, so operators can run it anywhere.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(HERE, "dashboard.html")

BEGIN = "# --- BEGIN dashboard (#845 authenticated fleet dashboard) ---"
END = "# --- END dashboard ---"

DEFAULT_WORKER_PATH = os.path.join(
    "/home/hatch/workspace/goals",
    "sparkvm-dev-website-v2-cloudflare-management-infra",
    "control-plane/worker.py",
)

# Header comment lines the sync writes between the BEGIN marker and the
# DASHBOARD_HTML assignment. Kept canonical here so the block the script
# produces is stable no matter how the plane-side copy was hand-edited.
HEADER_LINES = [
    "# Canonical source: spark-vm repo hosted/dashboard/dashboard.html.",
    "# This inlined copy MUST stay byte-identical; the repo's",
    "# hosted/dashboard/test_dashboard.py asserts that when the worker",
    "# source is reachable. The Worker deploys as a single file.",
]


class SyncError(Exception):
    """sync_dashboard's failure mode: loud, never half-written."""


def resolve_worker_path():
    """Shared with test_dashboard: env override, then the default."""
    return os.environ.get("SPARKVM_WORKER_PATH", DEFAULT_WORKER_PATH)


def _load_html():
    with open(HTML_PATH, encoding="utf-8") as f:
        html = f.read()
    if not html:
        raise SyncError("dashboard.html is empty — refusing to inline")
    if '"""' in html:
        raise SyncError('dashboard.html contains """ — it would terminate '
                        "the inlined Python string in worker.py")
    trailing_bs = len(html) - len(html.rstrip("\\"))
    if trailing_bs % 2 == 1:
        raise SyncError("dashboard.html ends with an odd number of "
                        "backslashes — the last one would escape the closing "
                        '""" of the inlined string in worker.py')
    if not html.startswith("<!DOCTYPE html>"):
        raise SyncError("dashboard.html does not start with <!DOCTYPE html> "
                        "— refusing to inline the wrong file")
    return html


def _rewrite(src, html):
    """Return the worker source with the dashboard block replaced.

    Only the region between the BEGIN marker line and the END marker
    line is touched; everything else (including the header comments,
    rewritten canonically) is preserved byte-for-byte.
    """
    if src.count(BEGIN) != 1:
        raise SyncError("BEGIN marker found %d times (want exactly 1)"
                        % src.count(BEGIN))
    if src.count(END) != 1:
        raise SyncError("END marker found %d times (want exactly 1)"
                        % src.count(END))
    begin_at = src.index(BEGIN)
    try:
        begin_eol = src.index("\n", begin_at)
    except ValueError:
        raise SyncError("BEGIN marker is the last line of worker.py with no "
                        "newline after it — refusing to inline")
    end_at = src.index(END)
    if not begin_eol < end_at:
        raise SyncError("END marker is not on a later line than BEGIN "
                        "— refusing")
    # Keep the whole END line (indentation included) — symmetric with the
    # BEGIN side, which keeps everything up to the BEGIN line's newline.
    end_line_start = src.rfind("\n", 0, end_at) + 1
    inner = ("\n".join(HEADER_LINES) + "\n"
             + 'DASHBOARD_HTML = """' + html + '"""')
    return src[:begin_eol] + "\n" + inner + "\n" + src[end_line_start:]


def sync(worker_path, check=False):
    """Re-inline dashboard.html into worker_path.

    Returns True when the worker was already in sync, False when it was
    (or would be, under --check) rewritten.
    """
    html = _load_html()
    try:
        with open(worker_path, encoding="utf-8") as f:
            src = f.read()
    except OSError as e:
        raise SyncError("cannot read worker.py at %s: %s" % (worker_path, e))
    new_src = _rewrite(src, html)
    if new_src == src:
        print("in sync: %s" % worker_path)
        return True
    if check:
        print("DRIFT: worker.py's inlined dashboard.html differs from "
              "dashboard.html — run sync_dashboard.py to re-inline")
        return False
    tmp = worker_path + ".sync-tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(new_src)
    # Keep the worker file's mode on the replacement (os.replace alone
    # would mint fresh default permissions).
    os.chmod(tmp, os.stat(worker_path).st_mode)
    os.replace(tmp, worker_path)
    print("synced: %s" % worker_path)
    return False


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--worker", default=None,
                   help="worker.py path (default: SPARKVM_WORKER_PATH or "
                        "the built-in default)")
    p.add_argument("--check", action="store_true",
                   help="exit 1 if the inlined copy has drifted; no write")
    args = p.parse_args(argv)
    worker_path = args.worker or resolve_worker_path()
    try:
        in_sync = sync(worker_path, check=args.check)
    except SyncError as e:
        print("sync_dashboard: %s" % e, file=sys.stderr)
        return 2
    return 0 if (in_sync or not args.check) else 1


if __name__ == "__main__":
    sys.exit(main())
