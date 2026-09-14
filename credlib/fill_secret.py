"""fill_secret — Playwright secret insertion, mirroring the cell's credential_fill.

fill_secret(page, selector, credential_name, entry_name="access_token")
resolves the entry via dynamic_credentials (same names as the cell),
reads the real value, and fills it into the page field. The value is
never printed, returned, or logged by this helper.

HONEST LIMIT: unlike the cell — where a separate browser agent fills
protected fields and the value never reaches the orchestrating agent —
here the value IS loaded into this process's memory while filling. If an
agent calls this directly, the secret exists in that agent's process
memory (though it never enters the visible transcript or context). For
agent-driven browser work, prefer the swap-proxy path instead:
put hsurr:<name> placeholders in traffic and let the proxy swap them.
This helper is for human-driven or isolated automation contexts.
"""

import re
import subprocess

from dynamic_credentials import (
    DynamicCredentialError,
    dynamic_credential_entry,
)

SUDO = ["sudo", "-n", "-u", "swapd"]
STORE = "/home/swapd/secrets"
ENTRY_LINE_RE = re.compile(r"^([A-Za-z0-9_-]+)=(.*)$", re.DOTALL)


def _read_value(credential_name, entry_name):
    """Read the raw secret value for one entry. Never logs or prints it."""
    p = subprocess.run(
        SUDO + ["/usr/bin/cat", "%s/%s" % (STORE, credential_name)],
        capture_output=True, check=False, timeout=10,
    )
    if p.returncode != 0:
        raise DynamicCredentialError(
            "credential '%s' not set \u2014 add with: cred set %s"
            % (credential_name, credential_name))
    text = p.stdout.decode("utf-8")
    lines = text.splitlines()
    # Multi-entry file? ("entry=value" per line) — mirrors the proxy addon.
    parsed = {}
    multi = bool(lines) and all(ENTRY_LINE_RE.match(l) for l in lines if l.strip())
    if multi:
        for line in lines:
            if not line.strip():
                continue
            m = ENTRY_LINE_RE.match(line)
            parsed[m.group(1)] = m.group(2)
        if entry_name in parsed:
            return parsed[entry_name]
        raise DynamicCredentialError(
            "credential '%s' has no entry '%s'" % (credential_name, entry_name))
    return text.strip()


def fill_secret(page, selector, credential_name, entry_name="access_token"):
    """Fill a Playwright field with a secret value. Returns None."""
    # Resolve through the same interface as the cell (validates the name,
    # raises DynamicCredentialError on problems) — discard the surrogate.
    dynamic_credential_entry(credential_name, entry_name=entry_name)
    value = _read_value(credential_name, entry_name)
    try:
        page.fill(selector, value)
    finally:
        # Drop our reference as soon as the fill is issued.
        del value
