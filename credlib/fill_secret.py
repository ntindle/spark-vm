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

MEMORY HYGIENE (issue #730): fill_secret practices overwrite-on-delete.
The store output is read into a bytearray this module owns (scrubbed
deterministically after decoding), and the decoded value plus any
multi-entry losers are scrubbed in place via _zero_str as soon as they
are no longer needed — `del` alone never zeroizes a CPython buffer, so
without this the plaintext lingers in the heap until the allocator
reuses it. _zero_str is best-effort and fail-safe: it only touches a
buffer whose layout it positively verified for that exact object and
silently skips anything else (non-CPython runtimes, exotic layouts),
so the worst case is today's behavior, never memory corruption. Honest
residual: transient temporaries the read path cannot deterministically
track; the layout-verification probe's single encode() bytes temporary
(one per _zero_str call — the probe reads into scrubbed bytearrays and
compares without copying, so this is the honest minimum); 1-char
latin-1 values, which CPython caches process-wide and are therefore
never scrubbed (scrubbing one would corrupt every future use of that
character in the process); the subprocess stdout bytes object itself
(the raw store output — it may be shared, e.g. by test doubles, so only
the owned bytearray copy is scrubbed and the original lingers per the
pre-#730 behavior); the sudo reader child process's own transient
memory; copies inside Playwright / the browser / the OS; and
allocator-level copies are all outside this scrubbing.
"""

import ctypes
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


def _scrub_bytearray(buf):
    """Deterministically overwrite a bytearray in place. Portable — a
    bytearray exposes a writable buffer by design, so no ctypes and no
    layout assumptions. Never raises."""
    try:
        buf[:] = b"\x00" * len(buf)
    except Exception:
        pass


def _str_buffer_span(s):
    """Return (offset, length) of s's character-data buffer, or None.

    The offset is derived per object as
    ``sys.getsizeof(s) - (len(s) + 1) * kind`` — no hardcoded header
    constants — and then POSITIVELY VERIFIED by reading the bytes at
    that span and comparing them against the known encoding of the
    content. If the read-back does not match, the layout assumption is
    wrong for this object/build and None is returned: the caller must
    skip scrubbing rather than touch unverified memory. Never raises.
    """
    try:
        n = len(s)
        if n == 0:
            return None
        if s.isascii():
            kind, codec = 1, "ascii"
        else:
            # CPython uses 1-byte kind for maxchar <= 0xFF (latin-1), not
            # only for pure ascii — missing this silently skips scrubbing
            # for very ordinary passwords.
            mx = max(map(ord, s))
            if mx <= 0xFF:
                kind, codec = 1, "latin-1"
            elif mx < 0x10000:
                kind, codec = 2, "utf-16-le"
            else:
                kind, codec = 4, "utf-32-le"
        size = sys.getsizeof(s)
        data_len = n * kind
        off = size - (n + 1) * kind
        if off <= 0 or data_len <= 0:
            return None
        # Self-verifying probe: the bytes at the computed span must be
        # exactly the content's encoding. Read into a bytearray (not an
        # immutable bytes temp) and compare without copying, scrubbing
        # both buffers afterwards — a dropped immutable temp would be
        # another lingering plaintext copy, the very thing #730
        # eliminates. One unavoidable temp remains: the encode() bytes
        # (see the module docstring's honest residual).
        raw = bytearray(data_len)
        ctypes.memmove((ctypes.c_char * data_len).from_buffer(raw),
                       id(s) + off, data_len)
        expected = bytearray(s.encode(codec))
        try:
            if raw != expected:
                return None
        finally:
            _scrub_bytearray(raw)
            _scrub_bytearray(expected)
        return (off, data_len)
    except Exception:
        return None


def _zero_str(s):
    """Best-effort in-place zeroing of a str's character buffer (#730).

    Only ever call this on str objects created on THIS module's read
    path (fresh decode/match/slice results) — never on literals,
    interned strings, or caller-provided objects, whose buffers may be
    shared. The span is verified per object by _str_buffer_span; an
    unverifiable layout is silently skipped, so the worst case is no
    scrubbing, never corruption. Never raises.

    Two hard no-scrub cases, both cheap identity checks: non-str
    objects (defense in depth — a lying __sizeof__ can't push the
    probe out of bounds anyway), and 1-char latin-1 strings, which
    CPython caches process-wide (unicode_latin1) — zeroing one would
    corrupt every future use of that character in the process.

    Note: a scrubbed object keeps its stale cached hash; harmless —
    every call site drops the object immediately after scrubbing.
    """
    try:
        if type(s) is not str:
            return
        if len(s) == 0:
            return
        if len(s) == 1 and s is chr(ord(s)):
            # Process-global latin-1 cache singleton: shared, never scrub.
            return
        span = _str_buffer_span(s)
        if span is None:
            return
        off, data_len = span
        ctypes.memset(id(s) + off, 0, data_len)
    except Exception:
        pass


def _scrub_temp(obj, owner):
    """Scrub a transient str slice unless it aliases the owner's buffer.

    Centralizes the CPython identity-subtlety rule in one place:
    str.strip() returns the SAME object when nothing is stripped, and a
    full slice of a str IS the same object — never scrub what might be
    the caller's buffer. Scrubbing the same temp twice is idempotent.
    """
    if obj is not owner:
        _zero_str(obj)


def _scan_multi_marker(text):
    """Scan for the multi-entry marker; return (is_multi, body_pos).

    Only the first non-blank line can be the explicit "#hsurr:multi"
    marker — mirrors proxy/swap_addon.py. Unmarked files are a single
    whole secret, even when they look like k=v lines (e.g. a base64
    token ending in "=="). body_pos is the offset just past the marker
    line, where entry parsing starts.

    Scans with find() instead of splitlines() so lines are not all
    copied up front; the small slices this creates are scrubbed before
    return. Never raises for well-formed str input.
    """
    pos = 0
    n = len(text)
    while True:
        nl = text.find("\n", pos)
        if nl < 0:
            line = text[pos:]
            end = True
        else:
            line = text[pos:nl]
            end = False
        stripped = line.strip()
        try:
            if stripped:
                return (stripped == MULTI_MARKER, n if end else nl + 1)
        finally:
            _scrub_temp(stripped, text)
            _scrub_temp(line, text)
        if end:
            return (False, n)
        pos = nl + 1


def _parse_entry_table(text, start):
    """Parse k=v lines after the multi marker into {entry: value}.

    Mirrors proxy/swap_addon.py: lines that do not match k=v are
    dropped. Values are fresh str objects owned by the returned dict;
    the caller scrubs the ones it does not keep. Consumed line slices
    are scrubbed as they go. Entry names (keys) are not secrets and
    are left alone.

    Known divergence from the old splitlines() scan (exotic): a lone
    interior \r as a line separator (pre-OSX line endings) is not
    treated as a break here; CRLF (\r\n) is handled above.
    """
    parsed = {}
    pos = start
    n = len(text)
    while pos <= n:
        nl = text.find("\n", pos)
        if nl < 0:
            line = text[pos:]
            end = True
        else:
            line = text[pos:nl]
            end = False
        if line.endswith("\r"):
            # CRLF store files (written/pasted from Windows): the old
            # splitlines()-based scan dropped the \r, but find("\n")
            # does not — without this the \r lands inside the value and
            # the wrong secret gets filled. line[:-1] is a new object
            # (or the 1-char singleton, which _zero_str refuses), so the
            # `is not text` aliasing guard below still holds.
            line = line[:-1]
        stripped = line.strip()
        try:
            if stripped:
                m = ENTRY_LINE_RE.match(line)
                if m:
                    key, val = m.group(1), m.group(2)
                    old = parsed.get(key)
                    if old is not None and old is not val:
                        # Duplicate entry name: the overwritten value
                        # would otherwise orphan its buffer unscubbed.
                        _zero_str(old)
                    parsed[key] = val
        finally:
            _scrub_temp(stripped, text)
            _scrub_temp(line, text)
        if end:
            break
        pos = nl + 1
    return parsed


def _extract_entry(text, credential_name, entry_name):
    """Split one entry out of the decoded store text.

    Verbatim contract (#88) preserved: the returned value is the stored
    bytes decoded with no strip/copy normalization.

    Memory hygiene (#730): every secret-bearing buffer this function
    creates but does NOT return is scrubbed before it goes out of
    scope — multi-entry losers and the decoded text itself when the
    value came from the entry table. The returned value is the caller's
    to scrub (fill_secret does so right after page.fill); it is always
    a fresh object from this read path, safe for _zero_str.
    """
    is_multi, body_pos = _scan_multi_marker(text)
    if not is_multi:
        # Single-secret file: the value IS the whole text, verbatim.
        return text
    parsed = _parse_entry_table(text, body_pos)
    found = entry_name in parsed
    keep = parsed[entry_name] if found else None
    for value in parsed.values():
        if value is not keep:
            _zero_str(value)
    # `keep` is always a fresh match-group str (or None when not found),
    # never `text` itself — scrub unconditionally.
    _zero_str(text)
    if not found:
        raise DynamicCredentialError(
            "credential '%s' has no entry '%s'" % (credential_name, entry_name))
    return keep


def _read_value(credential_name, entry_name):
    """Read the raw secret value for one entry. Never logs or prints it.

    The name and entry are validated before touching the filesystem.
    The actual read goes through the narrow reader
    /usr/local/bin/cred-store-get (sudoers-allowlisted, name-validating,
    exec-cats the fixed path /home/swapd/secrets/<name> — issue #669),
    so no unvalidated name can reach a raw cat ("../../etc/passwd"
    would be a path traversal read as swapd).

    Memory hygiene (#730): the captured stdout is copied into a
    bytearray this module owns — the bytes object subprocess hands us
    may be shared (or a test stub's literal), so it is never scrubbed
    directly and lingers per the pre-#730 behavior — and the bytearray
    is deterministically scrubbed after decoding. See _extract_entry
    for the decoded side.
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
    buf = bytearray(p.stdout)
    try:
        text = buf.decode("utf-8")
        return _extract_entry(text, credential_name, entry_name)
    finally:
        _scrub_bytearray(buf)


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
        # Overwrite-on-delete (#730): `del` alone drops the reference
        # but CPython never zeroizes the buffer, leaving the plaintext
        # in the heap until the allocator reuses it. Scrub the buffer
        # first — the value is always a fresh object from _read_value,
        # safe for _zero_str — then drop the reference. What was filled
        # is unaffected: scrubbing happens after page.fill returns.
        _zero_str(value)
        del value
