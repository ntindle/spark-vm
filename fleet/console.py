#!/usr/bin/env python3
"""G21 S2 operator fleet console (issue #795). Consumes the S1 read API.

A read-only, stdlib-only terminal console over the fleet read API
(``fleet/api.py``, ``docs/FLEET_READ_API_SPEC.md`` §6 "Console (G21
S2)"): the wave board and alert board consume *this API*, not the
journals directly — the API is the console's contract.

Boards:

- **alert board** — ``GET /fleet/alerts``. Pending rows render exactly
  like the ``fleet events watch`` CLI (the conformance test pins this),
  followed by the acknowledged tail, clearly labeled. The ack hint
  carries the real alert id so it is copy-pasteable; the console
  itself never acks — there is no write path anywhere in this module.
- **wave board** — ``GET /fleet/waves``. Until G15 S2 lands the endpoint
  serves the reserved shape, and the board says so in plain operator
  language first, with the API's own named reason on the line below —
  an empty wave list would read as "no waves", which is
  fail-dangerous.

Posture: no writes anywhere (no journal writes, no API writes — the API
is read-only anyway), no new producer, no box-side change. The ``--api``
host must be loopback: the S1 API binds 127.0.0.1 with no auth by
design, so the console refuses a non-loopback target fail-fast rather
than render an unauthenticated operator view of the wrong machine.
(The fetch path also bypasses any configured HTTP proxy, so the
loopback guarantee does not depend on the operator's ``no_proxy``.)

Exit codes (``--once``, the default): 1 when unacknowledged alerts are
pending — the same paging semantic as ``fleet events watch`` — 2 when
the API cannot be reached, 64 on a usage/config error (non-loopback
``--api``, non-positive ``--timeout``/``--watch``). ``--watch`` loops
until interrupted and always exits 0 on a clean Ctrl-C.
"""

import argparse
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from urllib.parse import urlparse

FLEET = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, FLEET)
import events  # noqa: E402  (fleet/ is not a package; same-dir import)

LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}

_CONSOLE_VERSION = "g21-s2/1"

# The loopback guarantee must not depend on the operator's proxy
# environment: bypass any configured HTTP proxy so a request to the
# unauthenticated localhost API can never route through an egress
# proxy when no_proxy omits localhost.
_NO_PROXY_OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}))


class ConsoleError(Exception):
    """A usage/config error: the console refuses to run."""


class FetchError(Exception):
    """The API could not be reached or did not speak JSON."""


def api_host_is_loopback(base_url):
    """True iff the --api target is a loopback host.

    The S1 API is unauthenticated and localhost-only by construction;
    aiming the console anywhere else is either a typo or a leak of an
    operator view, so it fails closed here.
    """
    try:
        host = urlparse(base_url).hostname or ""
    except ValueError:
        return False
    host = host.lower()
    if host in LOOPBACK_HOSTS:
        return True
    if host.startswith("127."):
        # 127.0.0.0/8 — all loopback, urlparse hands us the bare host.
        try:
            octets = host.split(".")
            return len(octets) == 4 and all(
                0 <= int(o) <= 255 for o in octets)
        except ValueError:
            return False
    return False


def fetch_json(base_url, path, timeout):
    """GET one API path. Returns (http_status, body_dict).

    Raises FetchError when the API is unreachable or answers
    non-JSON — the console renders those honestly rather than
    guessing at a board.
    """
    url = base_url.rstrip("/") + path
    req = urllib.request.Request(url, headers={
        "User-Agent": "sparkvm-fleet-console/%s" % _CONSOLE_VERSION})
    try:
        with _NO_PROXY_OPENER.open(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            # Not the API (or a proxy in the middle): scrub before the
            # operator's terminal ever sees it.
            return exc.code, {"error": events._clean_text(raw)[:200]}
    except (urllib.error.URLError, ValueError, TimeoutError,
            OSError, json.JSONDecodeError) as exc:
        raise FetchError("cannot reach the fleet API at %s: %s"
                         % (url, exc))


def _as_of_line(body):
    as_of = body.get("data_current_as_of")
    return ("  (fleet data current as of %s)"
            % events._clean_text(str(as_of))) if as_of else None


def _alert_lines(alerts):
    """Render alert rows exactly like ``fleet events watch`` (conformance).

    The field formats are the CLI's: ``to`` is the CLI's display
    truncation, ``fired_at`` is the ISO prefix, and ``detail``/ids are
    control-char stripped. The acked tail is the console's own addition
    — marked as such, since the CLI omits acked alerts.
    """
    lines = []
    pending = [a for a in alerts if not a.get("acked")]
    acked = [a for a in alerts if a.get("acked")]
    if pending:
        lines.append("UNACKNOWLEDGED ALERTS (%d):" % len(pending))
        for a in pending:
            lines.append("  [%s] box=%s subcomponent=%s to=%s fired=%s" % (
                events._clean_text(a.get("rule")),
                events._clean_text(a.get("box_id")) or "-",
                events._clean_text(a.get("subcomponent")) or "-",
                events._short(a.get("to")),
                events._clean_text(
                    (events._str_or_none(a.get("fired_at")) or "?")[:19])))
            lines.append("      %s" % events._clean_text(a.get("detail") or ""))
            alert_id = events._clean_text(a.get("alert_id"))
            lines.append("      alert_id=%s (fleet events ack --alert-id %s)"
                         % (alert_id, alert_id))
    else:
        lines.append("no unacknowledged alerts")
    if acked:
        lines.append("ALREADY ACKNOWLEDGED:")
        for a in acked:
            lines.append(
                "  [%s] box=%s subcomponent=%s to=%s fired=%s "
                "acked_at=%s by=%s" % (
                    events._clean_text(a.get("rule")),
                    events._clean_text(a.get("box_id")) or "-",
                    events._clean_text(a.get("subcomponent")) or "-",
                    events._short(a.get("to")),
                    events._clean_text(
                        (events._str_or_none(a.get("fired_at")) or "?")[:19]),
                    events._clean_text(
                        (events._str_or_none(a.get("acked_at")) or "?")[:19]),
                    events._clean_text(a.get("acked_by")) or "unknown"))
    return lines


def render_alert_board(status, body):
    """Render the alert board from one /fleet/alerts response."""
    lines = []
    if not isinstance(body, dict):
        return ["ALERTS: unexpected response shape from the API"]
    if status != 200:
        err = body.get("error", "request failed")
        hint = body.get("hint", "")
        lines.append("ALERTS: API error (%s) — %s" % (
            status, events._clean_text(str(err))))
        if hint:
            lines.append("  hint: %s" % events._clean_text(str(hint)))
        return lines
    alerts = body.get("alerts")
    if not isinstance(alerts, list):
        return ["ALERTS: unexpected response shape from the API"]
    if not all(isinstance(a, dict) for a in alerts):
        return ["ALERTS: unexpected response shape from the API"]
    lines.append("ALERTS: %s — %d pending, %d acked" % (
        body.get("status", "?"), body.get("pending_count", 0),
        body.get("acked_count", 0)))
    lines.extend(_alert_lines(alerts))
    note = body.get("note")
    if note:
        lines.append("  note: %s" % events._clean_text(str(note)))
    as_of = _as_of_line(body)
    if as_of:
        lines.append(as_of)
    return lines


def render_wave_board(status, body):
    """Render the wave board from one /fleet/waves response.

    The reserved shape (G15 S2 unlanded) is reported in plain operator
    language first, with the API's own named reason on the line below —
    an empty wave list would read as "no waves", which is
    fail-dangerous. A future landed shape (non-empty ``waves``) renders
    each wave's fields one row per wave.
    """
    lines = []
    if not isinstance(body, dict):
        return ["WAVES: unexpected response shape from the API"]
    if status != 200:
        err = body.get("error", "request failed")
        lines.append("WAVES: API error (%s) — %s" % (
            status, events._clean_text(str(err))))
        return lines
    waves = body.get("waves")
    if not isinstance(waves, list):
        return ["WAVES: unexpected response shape from the API"]
    unavailability = body.get("wave_assignments")
    if not waves and isinstance(unavailability, str) and unavailability:
        lines.append("WAVES: wave tracking isn't available yet "
                     "(expected with G15 S2) — this board can't see "
                     "waves, which is not the same as no waves "
                     "being scheduled.")
        lines.append("  the API's own wording: %s"
                     % events._clean_text(unavailability))
        return lines
    if not waves:
        lines.append("WAVES: no waves recorded")
        return lines
    lines.append("WAVES (%d):" % len(waves))
    for wave in waves:
        if isinstance(wave, dict):
            wave_id = wave.get("wave_id") or wave.get("id") or "?"
            rest = {k: v for k, v in wave.items()
                    if k not in ("wave_id", "id")}
            lines.append("  %s: %s" % (
                events._clean_text(str(wave_id)),
                events._clean_text(json.dumps(rest, sort_keys=True))))
        else:
            lines.append("  %s" % events._clean_text(str(wave)))
    as_of = _as_of_line(body)
    if as_of:
        lines.append(as_of)
    return lines


def render_screen(base_url, boards):
    """Render one full console screen.

    ``boards`` maps "alerts"/"waves" to (status, body) tuples; a
    FetchError value in place of the tuple renders as an unreachable
    board rather than killing the whole screen.
    """
    lines = ["fleet console — %s" % base_url, ""]
    order = [b for b in ("alerts", "waves") if b in boards]
    for i, name in enumerate(order):
        if i:
            lines.append("")
        result = boards[name]
        if isinstance(result, FetchError):
            label = "ALERTS" if name == "alerts" else "WAVES"
            lines.append("%s: %s" % (label, result))
            continue
        status, body = result
        if name == "alerts":
            lines.extend(render_alert_board(status, body))
        else:
            lines.extend(render_wave_board(status, body))
    return "\n".join(lines)


def run_once(args):
    """Fetch the boards and print one screen. Returns the exit code."""
    boards = _fetch_all(args)
    failed = any(isinstance(result, FetchError)
                 for result in boards.values())
    print(render_screen(args.api, boards))
    if failed:
        return 2
    alerts = boards.get("alerts")
    if (isinstance(alerts, tuple) and alerts[0] == 200
            and isinstance(alerts[1], dict)):
        pending = alerts[1].get("pending_count", 0)
        return 1 if pending else 0
    return 0


def watch_header(interval_s):
    """One line proving the --watch screen is live, not frozen."""
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    return "rendered %s — refreshing every %ss (Ctrl-C to stop)" % (
        now, interval_s)


def run_watch(args):
    """Refresh the screen every --watch seconds until interrupted."""
    if not math.isfinite(args.watch) or args.watch <= 0:
        raise ConsoleError("--watch needs a positive finite interval")
    try:
        while True:
            screen = render_screen(args.api, _fetch_all(args))
            print("\x1b[2J\x1b[H" + watch_header(args.watch) + "\n\n"
                  + screen, flush=True)
            time.sleep(args.watch)
    except KeyboardInterrupt:
        print()
        return 0


def _fetch_all(args):
    boards = {}
    for name, path in (("alerts", "/fleet/alerts"),
                       ("waves", "/fleet/waves")):
        if args.board != "all" and args.board != name:
            continue
        try:
            boards[name] = fetch_json(args.api, path, args.timeout)
        except FetchError as exc:
            boards[name] = exc
    return boards


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="G21 S2 operator fleet console (issue #795): read-only "
                    "terminal boards over the fleet read API.")
    parser.add_argument("--api", default="http://127.0.0.1:18760",
                        help="fleet read API base URL (loopback only; "
                             "default http://127.0.0.1:18760)")
    parser.add_argument("--board", choices=("all", "alerts", "waves"),
                        default="all", help="which boards to render")
    parser.add_argument("--timeout", type=float, default=15.0,
                        help="per-request timeout in seconds (default 15)")
    parser.add_argument("--once", action="store_true",
                        help="print one screen and exit (the default; "
                             "accepted for symmetry with --watch)")
    parser.add_argument("--watch", type=float, default=None,
                        metavar="SECONDS",
                        help="refresh every SECONDS instead of --once "
                             "(an explicit 0 or non-positive value is a "
                             "usage error)")
    args = parser.parse_args(argv)
    if not api_host_is_loopback(args.api):
        print("error: --api must be a loopback host (the fleet read API "
              "is unauthenticated and localhost-only); got %r"
              % args.api, file=sys.stderr)
        return 64
    if args.timeout <= 0 or not math.isfinite(args.timeout):
        print("error: --timeout must be a positive finite number of "
              "seconds", file=sys.stderr)
        return 64
    if args.watch is not None:
        # Note: default=None means the flag was omitted (one-shot mode);
        # an explicit --watch 0 must NOT fall through to run_once — a zero
        # refresh interval is a usage error, not a silent one-shot.
        try:
            return run_watch(args)
        except ConsoleError as exc:
            print("error: %s" % exc, file=sys.stderr)
            return 64
    return run_once(args)


if __name__ == "__main__":
    sys.exit(main())
