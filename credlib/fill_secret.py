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
This helper is for human-driven or isolated automation contexts — and
that is now enforced at the call boundary (issue #671): fill_secret
refuses to run unless stdin is a real terminal or the caller explicitly
opts in with SPARKVM_FILL_SECRET_HUMAN_OVERRIDE=1. The direct read helper
_read_value is internal; reach it via fill_secret, not past it.
"""

import os
import re
import subprocess
import sys

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


# Opt-in marker for isolated (non-interactive) automation contexts, per
# issue #671: setting SPARKVM_FILL_SECRET_HUMAN_OVERRIDE=1 asserts that the
# caller is a human's automation, not an agent session, and accepts the
# HONEST LIMIT (the plaintext secret enters this process's memory).
_FILL_SECRET_HUMAN_OVERRIDE = "SPARKVM_FILL_SECRET_HUMAN_OVERRIDE"


def _require_human_context():
    """Refuse to proceed unless the caller is a human-driven context.

    fill_secret puts the plaintext secret into the calling process's
    memory (HONEST LIMIT above), which the never-see-secrets agent
    policy forbids for agent processes. The caller satisfies the guard
    by one of two routes:

    1. stdin is a real terminal — typically a person driving this shell;
    2. SPARKVM_FILL_SECRET_HUMAN_OVERRIDE=1 is set in the environment — an
       explicit, auditable opt-in by isolated (non-interactive)
       automation that owns the HONEST LIMIT. The opt-in is
       per-invocation intent, not a persistent grant: exporting it in a
       shell profile or a systemd unit defeats the control.

    Honest limit of this guard: isatty() is a property of the file
    descriptor, not a proof of human presence. This is a default-deny
    *heuristic* that fails closed for headless exec (pipes, cron,
    daemons); sessions on a pseudo-terminal — including tmux, which
    agent coding jobs run inside — present a TTY and pass it. The
    never-see-secrets guarantee for agents therefore remains the agent
    policy plus the swap-proxy path and store auditing, not this guard;
    the guard converts silent docstring violations into a loud refusal
    wherever headless execution would otherwise quietly proceed.

    Raises DynamicCredentialError otherwise. The direct read helper
    _read_value is internal (underscore) — the boundary is this
    function, called at the top of fill_secret, so the distinction the
    docstring asked for is now code, not discipline.
    """
    if os.environ.get(_FILL_SECRET_HUMAN_OVERRIDE) == "1":
        return
    stdin = sys.stdin
    try:
        is_tty = stdin is not None and stdin.isatty()
    except Exception:
        is_tty = False
    if is_tty:
        return
    raise DynamicCredentialError(
        "fill_secret refused: this process has no terminal on stdin and "
        "SPARKVM_FILL_SECRET_HUMAN_OVERRIDE=1 is not set (issue #671). "
        "fill_secret loads the plaintext secret into the calling "
        "process's memory; agent-driven browser work must use the "
        "swap-proxy path (hsurr:<name> placeholders swapped at the "
        "proxy) instead. Human-driven shells run with a terminal; "
        "isolated automation may set SPARKVM_FILL_SECRET_HUMAN_OVERRIDE=1 to "
        "opt in explicitly. Note: this guard is a default-deny heuristic, "
        "not proof of human presence — pseudo-terminal sessions (e.g. tmux, "
        "which agent jobs use) present a TTY and pass it; the "
        "never-see-secrets guarantee for agents remains the agent policy, "
        "the swap-proxy path, and store auditing."
    )


def fill_secret(page, selector, credential_name, entry_name="access_token"):
    """Fill a Playwright field with a secret value. Returns None.

    Human-context guard first: fill_secret loads the plaintext secret
    into this process's memory, so the never-see-secrets policy (issue
    #671) says agent-driven processes must use the swap-proxy path
    instead. See _require_human_context for the exact rule — including
    its honest limit: the guard is a default-deny heuristic, not a
    proof of human presence (PTY-backed sessions such as tmux present
    a TTY and pass it).
    """
    _require_human_context()
    # Resolve through the same interface as the cell (validates the name,
    # raises DynamicCredentialError on problems) — discard the surrogate.
    dynamic_credential_entry(credential_name, entry_name=entry_name)
    value = _read_value(credential_name, entry_name)
    try:
        page.fill(selector, value)
    finally:
        # Drop our reference as soon as the fill is issued.
        del value
