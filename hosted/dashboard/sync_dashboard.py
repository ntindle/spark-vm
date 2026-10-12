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
    ./sync_dashboard.py --write-snapshot         # regenerate the committed
                                                 # snapshot after editing
                                                 # dashboard.html
    ./sync_dashboard.py --extract > /tmp/w.html  # read-only: dump the
                                                 # worker's inlined block
                                                 # for forensics

The worker-path resolution is shared with the test module: the
``SPARKVM_WORKER_PATH`` environment variable overrides the default
(the loop VM's control-plane checkout).

The canonical-copy rule has a CI-visible half and a loop-VM half. The
committed snapshot ``dashboard.inlined.txt`` is the exact block sync
writes between the BEGIN/END markers, regenerated from
``dashboard.html`` by ``--write-snapshot``. The test suite asserts the
snapshot is byte-identical to what sync would write — that assertion
needs no worker checkout, so it runs on GitHub Actions: editing the
page without regenerating the snapshot fails CI. The byte-identity
test against the live worker copy still needs a reachable worker, so
it runs wherever the worker is reachable (the loop VM) and skips
elsewhere.

Never reverse-sync: the worker copy is never the source of truth. If
the deployed copy was hand-edited (diagnose with ``--extract``, diff
against ``dashboard.html``, hand-port the change into the canonical
page, then re-run ``--write-snapshot`` and sync). Pasting an extracted
block back into ``dashboard.html`` would re-import the hand-paste
corruption class the guards refuse (literal control bytes).

Stdlib only — no pytest needed, so operators can run it anywhere.
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(HERE, "dashboard.html")
SNAPSHOT_PATH = os.path.join(HERE, "dashboard.inlined.txt")

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


def render_inline_block(html):
    """The exact block sync writes between the BEGIN and END marker lines.

    One definition serves three consumers — `_rewrite` (the worker sync),
    `--write-snapshot` (the committed snapshot), and the snapshot-freshness
    test — so the snapshot and the worker copy cannot be produced by
    divergent code. Returns the region as a `str` (utf-8), exclusive of
    the marker lines' own newlines.
    """
    return ("\n".join(HEADER_LINES) + "\n"
            + 'DASHBOARD_HTML = """' + html + '"""')


class SyncError(Exception):
    """sync_dashboard's failure mode: loud, never half-written."""


def resolve_worker_path():
    """Shared with test_dashboard: env override, then the default."""
    return os.environ.get("SPARKVM_WORKER_PATH", DEFAULT_WORKER_PATH)


def raw_control_bytes(html):
    """Raw C0/C1 control characters in the page, tab/LF/CR excluded.

    Shared by the sync guard and the static test. The page's own
    control-byte handling is written with \\xNN *escape sequences* in its
    JS source — literal control bytes are never legitimate content.
    """
    return sorted({c for c in html
                   if (ord(c) < 32 and c not in "\t\n\r")
                   or 0x7F <= ord(c) <= 0x9F})


def _load_html():
    with open(HTML_PATH, encoding="utf-8") as f:
        html = f.read()
    if not html:
        raise SyncError("dashboard.html is empty — refusing to inline")
    if '"""' in html:
        raise SyncError('dashboard.html contains """ — it would terminate '
                        "the inlined Python string in worker.py")
    bad = raw_control_bytes(html)
    if bad:
        raise SyncError("dashboard.html contains raw control byte(s) %s — "
                        "the page must use \\xNN escape sequences, never "
                        "literal control bytes" %
                        ", ".join("U+%04X" % ord(c) for c in bad))
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
    inner = render_inline_block(html)
    return src[:begin_eol] + "\n" + inner + "\n" + src[end_line_start:]


def _extract_html(src):
    """The DASHBOARD_HTML string content of a worker's inlined block.

    Diagnostics only (--extract): read the block a hand-edit left behind
    so it can be diffed against dashboard.html and re-authored by hand.
    The extraction is byte-faithful and read-only; it never writes the
    repo source, and nothing here pastes the result back — that direction
    is refused by design (the sync guards reject the literal-control-byte
    corruption class that hand-pastes carry).
    """
    try:
        block = src.split(BEGIN)[1].split(END)[0]
    except IndexError:
        raise SyncError("dashboard block not found in worker.py "
                        "(missing BEGIN/END markers)")
    # Failure semantics differ from the test module's _inline_html (which
    # asserts): this is a CLI diagnostic, so a malformed block is a loud
    # SyncError, not an assertion. A worker carrying duplicated BEGIN
    # markers is itself a sync-refusal case; for forensics we read the
    # first block, which is the one the marker order defines.
    m = re.search(r'DASHBOARD_HTML = """(.*)"""\s*$', block, re.S)
    if not m:
        raise SyncError("dashboard block has no DASHBOARD_HTML assignment "
                        "after the BEGIN marker — the worker copy is "
                        "malformed")
    return m.group(1)


def _read_worker(worker_path):
    try:
        with open(worker_path, encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        raise SyncError("cannot read worker.py at %s: %s" % (worker_path, e))


def _write_snapshot():
    """Regenerate the committed inlined-block snapshot from dashboard.html.

    The snapshot is derived, not canonical — `_load_html` applies the same
    guards as the sync path, so a corrupt page fails the regeneration
    instead of producing a corrupt snapshot.
    """
    block = render_inline_block(_load_html())
    tmp = SNAPSHOT_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(block)
    os.replace(tmp, SNAPSHOT_PATH)


def sync(worker_path, check=False):
    """Re-inline dashboard.html into worker_path.

    Returns True when the worker was already in sync, False when it was
    (or would be, under --check) rewritten.
    """
    html = _load_html()
    src = _read_worker(worker_path)
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
    p.add_argument("--write-snapshot", action="store_true",
                   help="regenerate dashboard.inlined.txt from the current "
                        "dashboard.html; no worker touched")
    p.add_argument("--extract", action="store_true",
                   help="write the worker's inlined dashboard HTML bytes to "
                        "stdout (read-only diagnostics); no write")
    args = p.parse_args(argv)
    worker_path = args.worker or resolve_worker_path()
    try:
        if args.write_snapshot:
            _write_snapshot()
            print("snapshot written: %s" % SNAPSHOT_PATH)
            return 0
        if args.extract:
            html = _extract_html(_read_worker(worker_path))
            sys.stdout.buffer.write(html.encode("utf-8"))
            return 0
        in_sync = sync(worker_path, check=args.check)
    except SyncError as e:
        print("sync_dashboard: %s" % e, file=sys.stderr)
        return 2
    return 0 if (in_sync or not args.check) else 1


if __name__ == "__main__":
    sys.exit(main())
