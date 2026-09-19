#!/usr/bin/env python3
"""Demo scaffolding for spark-vm demo assets (marketing).

Runs confirmd with DEMO-ONLY overrides: the tailnet-identity auth gate is
bypassed (Handler._auth returns the owner) because the demo camera is
localhost, not a tailnet peer; and the filing gate (finding 50) is stubbed
(file_owner_name returns "swapd") because the demo files as the demo user,
not bdrive/swapd. Grant minting should point GRANT_WRITER at a stub that
exits 0 — the demo shows the approval UX, not grant issuance.

The demo shows the approval UX flow — pending page, tap-to-approve,
answered page — NOT the auth gate or the filing gate. Auth and filing are
the real code; only the identity checks are stubbed, and only for the demo.

This file is demo tooling, not shipped product code. It must never run in
production.
"""
import os
import sys

# Engineering review: hard fences so this can never become an
# unauthenticated approval server on the tailnet. The imported module
# reads BIND/CONFIRM_DIR/GRANT_WRITER at import time, so the fences go
# BEFORE the import.
if os.environ.get("CONFIRM_DEMO") != "1":
    sys.exit("demo_confirmd.py is DEMO-ONLY: set CONFIRM_DEMO=1 to run it.")
os.environ.setdefault("CONFIRM_BIND", "127.0.0.1")  # loopback only, always
if os.environ.get("CONFIRM_DIR", "") in ("", "/home/swapd/approvals"):
    sys.exit("demo_confirmd.py is DEMO-ONLY: point CONFIRM_DIR at a scratch "
             "directory, never the production approvals dir.")

sys.path.insert(0, os.environ.get("CONFIRM_SRC") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "confirm"))
import confirmd  # noqa: E402


def main():
    owner = os.environ.get("CONFIRM_OWNER", "ntindle@github")
    # DEMO-ONLY: bypass the tailnet-login peer check. See module docstring.
    confirmd.Handler._auth = lambda self: owner  # noqa: SLF001
    # DEMO-ONLY: the filing gate (finding 50) only accepts approvals filed
    # by bdrive/swapd, but the demo files as the demo user. Stub the owner
    # lookup so the demo exercises the full UX flow (approve -> grant mint
    # -> answered page). Audit lines in the demo therefore attribute the
    # requester as swapd — documented staging, never production.
    confirmd.file_owner_name = lambda path: "swapd"  # noqa: SLF001
    print("demo-confirmd: DEMO-ONLY auth + filing-gate bypasses active; "
          "do not use in production", flush=True)
    confirmd.main()


if __name__ == "__main__":
    main()
