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
    _validate_name,
    dynamic_credential_entry,
)

SUDO = ["sudo", "-n", "-u", "swapd"]
# Narrow reader for the swapd secret store (root-owned 0755, in
# proxy/sudoers-swapd): validates the name itself and exec-cats the
# fixed path /home/swapd/secrets/<name>. This is the ONLY granted read
# path for secret files — a raw `sudo ... cat /home/swapd/secrets/<name>`
# is NOT in the sudoers allowlist (issue #669) and is denied on the
# deployed box.
STORE_GET = "/usr/local/bin/cred-store-get"
ENTRY_LINE_RE = re.compile(r"^([A-Za-z0-9_-]+)=(.*)$", re.DOTALL)
# Explicit marker: a secret file whose first non-blank line is this is
# multi-entry. Mirrors proxy/swap_addon.py (MULTI_MARKER there).
MULTI_MARKER = "#hsurr:multi"


def _read_value(credential_name, entry_name):
    """Read the raw secret value for one entry. Never logs or prints it.

    The name and entry are validated before touching the filesystem.
    The actual read goes through the narrow reader
    /usr/local/bin/cred-store-get (sudoers-allowlisted, name-validating,
    exec-cats the fixed path /home/swapd/secrets/<name> — issue #669),
    so no unvalidated name can reach a raw cat ("../../etc/passwd"
    would be a path traversal read as swapd).
    """
    _validate_name(credential_name, "credential")
    _validate_name(entry_name, "entry")
    p = subprocess.run(
        SUDO + [STORE_GET, credential_name],
        capture_output=True, check=False, timeout=10,
    )
    if p.returncode != 0:
        # The reader's stderr distinguishes the cases (#147 class): a
        # missing file vs a broken read path. It never carries secret
        # values (validation + cat errors only), so surfacing the tail
        # is safe and keeps "not set" from masking a denied read.
        detail = p.stderr.decode("utf-8", "replace").strip()[-200:]
        hint = " (reader: %s)" % detail if detail else ""
        raise DynamicCredentialError(
            "credential '%s' not set%s \u2014 add with: cred set %s"
            % (credential_name, hint, credential_name))
    text = p.stdout.decode("utf-8")
    lines = [l for l in text.splitlines() if l.strip()]
    # Multi-entry file? Only when the first non-blank line is the explicit
    # "#hsurr:multi" marker — mirrors the proxy addon. Unmarked files are a
    # single whole secret, even when they look like k=v lines (e.g. a base64
    # token ending in "==").
    if not lines or lines[0].strip() != MULTI_MARKER:
        # Verbatim, never stripped (#88): write paths chomp exactly one
        # trailing newline exactly once — `cred set` stdin and cred-ui
        # paste at the frontend, cred-store-set-inference at its own
        # boundary; the narrow main writer (proxy/cred-store-set) stores
        # stdin verbatim and its frontends chomp first. So the stored
        # bytes ARE the intended value, and a read-side strip() corrupts
        # secrets that legitimately start/end with whitespace (stored
        # "a\n" would read back as "a"). Direct narrow-writer use must
        # pipe exact bytes (printf '%s', never echo).
        return text
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
