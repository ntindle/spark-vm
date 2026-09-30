"""credvalidate — single-source credential/entry/host validation contract.

Issue #706: the canonical credential-name, entry-name, and allowed-host
contract used to be implemented four times, independently — in the `cred`
CLI, `cred-ui/cred-ui.py`, `proxy/cred-registry-set`, and
`credlib/dynamic_credentials.py` — kept in sync only by comments pointing
at #150 ("human-grep synchronization on a security boundary"). Drift had
already happened once (the UI accepted ports and underscores the writer
rejected, producing a confusing post-store failure).

This file is the one place the contract text lives. Consumers:

- `credlib/dynamic_credentials.py` — same directory, direct import.
- `cred-ui/cred-ui.py` — `cred-ui/install.sh` stages this file flat next
  to `cred-ui.py` (like `bounded_http.py`); the import is unconditional,
  so a missing module fails the service loudly at startup instead of
  silently running unvalidated.
- `proxy/cred-registry-set` — `proxy/deploy.sh` installs this file next
  to the writer in /usr/local/bin (root-owned 0644, same install step, so
  the two update atomically); the wrapper resolves the module from its own
  script directory — never from caller input — and the import is
  unconditional, so a missing module fails every invocation loudly.
- `cred` — single-file CLI deployed as a manual copy with no installer,
  so there is no deploy unit to ship the module with. It keeps a
  machine-checked *mirror* of the contract atoms (bannered DO NOT EDIT);
  `credlib/test_credvalidate.py` asserts the mirror's atoms are identical
  to this module's, so the mirror cannot drift silently either.

Why not a fourth cross-domain artifact: the module ships *inside* each
unit's own artifact, atomically with that unit — there is no shared
runtime file whose update could skew one unit against another. The one
unit without an installer (`cred`) is covered by the parity test instead
of a runtime import, which would have made this module dead code in
production while a fallback copy did the real work.

The module owns the *decision* (accept/reject); each consumer owns its
*presentation*: every validator raises ValueError with a minimal message,
and consumers map it to their own error type (CredentialError, fail(),
False, DynamicCredentialError) with their own wording. Behavior on every
previously-valid input is unchanged.

Stdlib only. Non-string input is invalid (ValueError), never a TypeError —
callers must not need their own type guards to fail closed.
"""

import re

# Canonical name/entry charset + 64-char cap. Gates CREATION everywhere
# (cred set/register, cred-ui api_set, writer set/set-with-hosts).
NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# Legacy-tolerant name check (charset only, no cap) for management/read
# verbs: credentials created before the #150 caps must stay manageable
# without hand-editing the registry as root. Never gates creation.
NAME_LEGACY_RE = re.compile(r"^[A-Za-z0-9_-]+$")

# Dotted-hostname shape: exact hostname or a leading-dot subdomain entry
# (".example.com"), the same shape hosts.allow takes. No underscores, no
# ports (the swap addon strips ports when matching request hosts, so a
# port in the registry would be dead config anyway).
HOST_SHAPE_RE = re.compile(r"^\.?[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*$")

# Canonical host caps: whole name <= 253, each dot-separated label <= 63
# (DNS). Creation bindings (add-host) enforce these; remove-host stays
# shape-only so over-long legacy bindings stay removable.
HOST_MAX_LEN = 253
HOST_LABEL_MAX_LEN = 63

# Structural registry keys that must never become credential entries: an
# entry named "allowed_hosts" would clobber the host binding with a
# placement object (finding 34b). allowed_methods/allowed_paths are
# reserved for grant scoping, grants before the grant machinery lands.
RESERVED_ENTRIES = ("allowed_hosts", "allowed_methods", "allowed_paths",
                    "grants")


def _reject(kind, value):
    raise ValueError("invalid %s %r" % (kind, value))


def check_name(name):
    """Canonical name check (creation): charset [A-Za-z0-9_-], 1-64 chars."""
    if not isinstance(name, str) or not NAME_RE.match(name):
        _reject("name", name)
    return name


def check_name_legacy(name):
    """Legacy-tolerant name check (management/read): charset only."""
    if not isinstance(name, str) or not NAME_LEGACY_RE.match(name):
        _reject("name", name)
    return name


def check_entry(name):
    """Creation-path entry check: canonical name + reserved guard."""
    check_name(name)
    if name in RESERVED_ENTRIES:
        raise ValueError("reserved entry name %r" % (name,))
    return name


def check_entry_legacy(name):
    """Management-path entry check: legacy name + reserved guard."""
    check_name_legacy(name)
    if name in RESERVED_ENTRIES:
        raise ValueError("reserved entry name %r" % (name,))
    return name


def check_host(host):
    """Canonical host check (new bindings): dotted shape + length caps.

    Returns the lowercased host (registry keys are case-folded).
    """
    if not isinstance(host, str):
        _reject("host", host)
    lowered = host.lower()
    if (len(lowered) > HOST_MAX_LEN or not HOST_SHAPE_RE.match(lowered)
            or any(len(label) > HOST_LABEL_MAX_LEN
                   for label in lowered.lstrip(".").split("."))):
        _reject("host", host)
    return lowered


def check_host_legacy(host):
    """Shape-only host check (remove-host): over-long legacy bindings stay
    removable. Returns the lowercased host."""
    if not isinstance(host, str):
        _reject("host", host)
    lowered = host.lower()
    if not HOST_SHAPE_RE.match(lowered):
        _reject("host", host)
    return lowered
