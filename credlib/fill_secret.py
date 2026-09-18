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
# Explicit marker: a secret file whose first non-blank line is this is
# multi-entry. Mirrors proxy/swap_addon.py (MULTI_MARKER there).
MULTI_MARKER = "#hsurr:multi"


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
    lines = [l for l in text.splitlines() if l.strip()]
    # Multi-entry file? Only when the first non-blank line is the explicit
    # "#hsurr:multi" marker — mirrors the proxy addon. Unmarked files are a
    # single whole secret, even when they look like k=v lines (e.g. a base64
    # token ending in "==").
    if not lines or lines[0].strip() != MULTI_MARKER:
        return text.strip()
    parsed = {}
    for line in lines[1:]:
        m = ENTRY_LINE_RE.match(line)
        if m:
            parsed[m.group(1)] = m.group(2)
        # Lines that don't match k=v are dropped (the proxy does the same).
    if entry_name in parsed:
        return parsed[entry_name]
    raise DynamicCredentialError(
        "credential '%s' has no entry '%s'" % (credential_name, entry_name))


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
