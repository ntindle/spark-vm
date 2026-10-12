"""Post-deploy cron-trigger verification for the plane Worker (#1069).

The silently-unwired failure mode: the plane workspace deploys the
`scheduled` handler but never registers the cron trigger, so nothing
ever ticks. A handler that runs proves nothing about the trigger
registration — this script asserts, against the live Cloudflare Workers
API or a saved JSON fixture, that every trigger in the contract
(`CRON_TRIGGER_CONTRACT.md`) is registered on the worker script.

Secrets: the API token is read from ``CF_API_TOKEN`` only and is never
printed, logged, or included in any output. The account id and script
name come from flags. Nothing in this module mutates anything — it is
a read-only assertion, safe to run in CI (via ``--fixture``) and from
the operator laptop.

Exit codes: 0 = every expected trigger present; 1 = one or more
expected triggers missing (names them); 2 = usage / API / parse error.
Extra cron schedules not in the contract are listed as informational
only — the plane legitimately carries triggers this contract does not
own (e.g. the #1013 phone-home GC).
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

# The contract's expected cron set. (cron, why) — kept here in one
# place so the verifier and the contract doc cannot drift; the
# contract doc reprints this table and cites it.
EXPECTED_TRIGGERS = (
    # D66: per-minute sweep — reminders, then digests, then watchers.
    ("* * * * *", "D9 push sweep (reminders + digests + watchers) — #1069"),
    # D89–D95 retention sweeper: daily is plenty, the bound is 90 days
    # and the sweep is idempotent. Off the top of the hour to dodge
    # cron-stampede on shared Workers cron infrastructure.
    ("30 3 * * *", "push retention GC (90-day bound) — #1298"),
)

API_BASE = "https://api.cloudflare.com/client/v4"
_TOKEN_ENV = "CF_API_TOKEN"


def normalize_cron(cron):
    """Collapse whitespace in a cron string so equivalent entries match."""
    return " ".join(str(cron).split())


def parse_schedules(doc):
    """Extract the set of normalized cron strings from a Workers-API
    schedules payload (or a saved fixture of one).

    The live response shape is ``{"result": [{"cron": "* * * * *",
    ...}], "success": true}``. Raises ValueError on a malformed
    payload — never on an empty-but-valid one (an empty list is the
    silently-unwired state this script exists to catch).
    """
    if not isinstance(doc, dict):
        raise ValueError("schedules payload must be a JSON object")
    result = doc.get("result")
    if not isinstance(result, list):
        raise ValueError("schedules payload has no 'result' list")
    crons = set()
    for entry in result:
        if not isinstance(entry, dict) or "cron" not in entry:
            raise ValueError("schedules entry missing 'cron' field")
        crons.add(normalize_cron(entry["cron"]))
    return crons


def check_triggers(expected, actual):
    """Compare the contract's expected set against the registered set.

    Returns (missing, extras): expected entries not registered, and
    registered crons the contract does not own. Extras are
    informational — they never fail the check.
    """
    missing = [(cron, why) for cron, why in expected
               if normalize_cron(cron) not in actual]
    expected_set = {normalize_cron(cron) for cron, _ in expected}
    extras = sorted(actual - expected_set)
    return missing, extras


def fetch_schedules(account_id, script_name, api_token):
    """Read the registered cron triggers via the Workers API. Read-only.

    The token travels only in the Authorization header; it is never
    part of any message this function raises.
    """
    url = (API_BASE + "/accounts/" + account_id
           + "/workers/scripts/" + script_name + "/schedules")
    req = urllib.request.Request(url)
    req.add_header("Authorization", "Bearer " + api_token)
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
    except urllib.error.HTTPError as exc:
        # The token must not appear in the error — only the status.
        raise RuntimeError(
            "Workers API returned HTTP %s for the schedules list"
            % exc.code) from None
    except urllib.error.URLError as exc:
        raise RuntimeError("Workers API request failed: %s" % exc.reason
                           ) from None
    try:
        doc = json.loads(body)
    except ValueError as exc:
        raise RuntimeError("Workers API returned non-JSON: %s" % exc
                           ) from None
    if not doc.get("success", False):
        errors = doc.get("errors", [])
        raise RuntimeError(
            "Workers API reported failure: %s" % (errors or "no detail"))
    return parse_schedules(doc)


def load_fixture(path):
    with open(path, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    return parse_schedules(doc)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Verify the plane Worker's cron triggers are "
                    "registered (#1069).")
    parser.add_argument("--account-id", default=os.environ.get("CF_ACCOUNT_ID"),
                        help="Cloudflare account id (or CF_ACCOUNT_ID). "
                             "Not needed with --fixture.")
    parser.add_argument("--script-name", default="sparkvm-control",
                        help="Worker script name (default: sparkvm-control).")
    parser.add_argument("--fixture",
                        help="Path to a saved schedules-list JSON payload; "
                             "skips the live API call (CI/offline mode).")
    args = parser.parse_args(argv)

    if args.fixture:
        try:
            actual = load_fixture(args.fixture)
        except (OSError, ValueError) as exc:
            print("error: cannot read fixture: %s" % exc, file=sys.stderr)
            return 2
    else:
        api_token = os.environ.get(_TOKEN_ENV)
        if not api_token:
            print("error: set %s (env) to query the live Workers API, "
                  "or use --fixture" % _TOKEN_ENV, file=sys.stderr)
            return 2
        if not args.account_id:
            print("error: --account-id or CF_ACCOUNT_ID is required",
                  file=sys.stderr)
            return 2
        try:
            actual = fetch_schedules(args.account_id, args.script_name,
                                     api_token)
        except RuntimeError as exc:
            # exc never carries the token (see fetch_schedules).
            print("error: %s" % exc, file=sys.stderr)
            return 2

    missing, extras = check_triggers(EXPECTED_TRIGGERS, actual)
    for cron in extras:
        print("note: extra cron schedule not in the contract: %s" % cron)
    if missing:
        print("FAIL: %d expected cron trigger(s) not registered on '%s':"
              % (len(missing), args.script_name))
        for cron, why in missing:
            print("  missing %r — %s" % (normalize_cron(cron), why))
        print("The handler is deployed but nothing will ever tick: "
              "register the triggers, then re-run this check. (#1069)")
        return 1
    print("ok: all %d contract cron triggers registered on '%s'"
          % (len(EXPECTED_TRIGGERS), args.script_name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
