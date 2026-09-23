"""dynamic_credentials — spark-vm port of the cell's dynamic credential helper.

Identical public interface: same function names, signatures, and
DynamicCredentialError. The ONLY intentional difference is transport:
the cell POSTs to authd's Unix socket; here entries resolve from the
local registry /home/swapd/credentials.json (read via `sudo -u swapd cat`,
since this runs as ntindle). A credential name with no registry entry
defaults to placement "bearer_header" with entry "access_token"
(zero-config common case).

Surrogate format is identical to the cell: hsurr:<credential_name>:<entry_name>.
The swapping proxy replaces these at request time, for allowlisted hosts only.
"""

import json
import re
import subprocess
import urllib.parse
import urllib.request

REGISTRY_PATH = "/home/swapd/credentials.json"
SUDO = ["sudo", "-n", "-u", "swapd"]


class DynamicCredentialError(Exception):
    """Raised for any credential resolution or placement problem."""


# Credential and entry names are interpolated into filesystem paths by
# some consumers (credlib/fill_secret.py reads
# /home/swapd/secrets/<name>), so they must be validated before use:
# no slashes, no dots, no shell. The swapd-side writers enforce
# charset-only (proxy/cred-store-set: ^[A-Za-z0-9_-]+$, no length cap),
# and the management/read verbs everywhere else are legacy-tolerant the
# same way (cred's check_name_legacy, cred-ui's NAME_LEGACY_RE,
# proxy/cred-registry-set's check_legacy) so credentials created before
# the #150 64-char cap stay usable. This choke point matches them:
# charset-only, no cap — and carries the NAME_LEGACY_RE identifier so
# the name states the semantics (per the arch review: NAME_RE means
# canonical "charset + 64-char cap" in cred and cred-ui; reusing it here
# for legacy semantics would be identifier drift on a security
# boundary). A 64-char cap here would reject names the writers and the
# swapping proxy still serve (finding, 2026-09-23 arch deep-read:
# surrogate building is a read path, not creation).
NAME_LEGACY_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _validate_name(value, what):
    """Reject anything that is not a safe credential/entry name.

    Shared with credlib/fill_secret.py (imported there): both the
    surrogate builders and the filesystem consumer validate through
    this one function so the choke point cannot drift. Legacy-tolerant
    (charset only): names predate the #150 cap and must stay resolvable.

    Raises DynamicCredentialError. The old check here (the surrogate
    "starts with hsurr:") was vacuous — the surrogate is constructed
    with that prefix — and validated nothing.
    """
    if not isinstance(value, str) or not NAME_LEGACY_RE.match(value):
        raise DynamicCredentialError(
            "invalid %s name %r (use only [A-Za-z0-9_-])"
            % (what, value))
    return value


# ---------------------------------------------------------------- registry

def _read_registry():
    """Return the registry dict (may be empty). Never raises on missing file."""
    try:
        p = subprocess.run(
            SUDO + ["/usr/bin/cat", REGISTRY_PATH],
            capture_output=True, check=False, timeout=10,
        )
    except FileNotFoundError:
        raise DynamicCredentialError("sudo not available on this box")
    except subprocess.TimeoutExpired:
        raise DynamicCredentialError("timed out reading the credential registry")
    if p.returncode != 0:
        return {}  # no registry yet: every name defaults
    try:
        data = json.loads(p.stdout.decode("utf-8"))
    except ValueError:
        raise DynamicCredentialError("credential registry is not valid JSON")
    if not isinstance(data, dict):
        raise DynamicCredentialError("credential registry must be a JSON object")
    return data


def dynamic_credential_entry(credential_name, entry_name="access_token", *, timeout=5.0):
    """Resolve one credential entry.

    Returns {"name": entry_name, "surrogate": "hsurr:<name>:<entry>",
             "placement": <placement>}. Placement comes from the registry
    (/home/swapd/credentials.json); unregistered names default to
    "bearer_header". Raises DynamicCredentialError on an invalid
    credential or entry name (names reach filesystem paths in some
    consumers, so validation happens here, at the choke point).
    """
    _validate_name(credential_name, "credential")
    _validate_name(entry_name, "entry")
    registry = _read_registry()
    placement = "bearer_header"
    entries = registry.get(credential_name)
    if isinstance(entries, dict):
        spec = entries.get(entry_name)
        if isinstance(spec, dict) and "placement" in spec:
            placement = spec["placement"]
    surrogate = "hsurr:%s:%s" % (credential_name, entry_name)
    return {"name": entry_name, "surrogate": surrogate, "placement": placement}


# ---------------------------------------------------------------- urls

def ensure_allowed_url(url, allowed_hosts):
    """Return the URL's host if allowlisted, else raise DynamicCredentialError.

    allowed_hosts: exact hostnames, or leading-dot entries matching
    subdomains (".example.com" matches "api.example.com").
    """
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    for entry in (allowed_hosts or []):
        e = entry.lower()
        if host == e or (e.startswith(".") and host.endswith(e)):
            return host
    raise DynamicCredentialError(
        "host %r is not in the allowed-hosts list" % (host,))


def url_with_surrogate_path_segment(url_template, credential_name, *,
                                    entry_name="access_token", allowed_hosts):
    """Build a URL with the surrogate placed into the path.

    url_template must contain a {surrogate} placeholder, e.g.
    "https://api.example.com/v1/{surrogate}/status".
    """
    entry = dynamic_credential_entry(credential_name, entry_name=entry_name)
    if "{surrogate}" not in url_template:
        raise DynamicCredentialError(
            "url_template must contain a {surrogate} placeholder")
    url = url_template.replace("{surrogate}", entry["surrogate"])
    ensure_allowed_url(url, allowed_hosts)
    return url


def url_with_surrogate_query_param(url, credential_name, *,
                                  entry_name="access_token", allowed_hosts):
    """Return url with the surrogate appended as a query parameter.

    The parameter name comes from the registry placement
    ({"query_param": "<name>"}); defaults to "access_token".
    """
    ensure_allowed_url(url, allowed_hosts)
    entry = dynamic_credential_entry(credential_name, entry_name=entry_name)
    placement = entry["placement"]
    param = "access_token"
    if isinstance(placement, dict) and "query_param" in placement:
        param = placement["query_param"]
    parts = urllib.parse.urlparse(url)
    q = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    q.append((param, entry["surrogate"]))
    return urllib.parse.urlunparse(parts._replace(query=urllib.parse.urlencode(q)))


# ---------------------------------------------------------------- requests

def add_surrogate_to_request(request, credential_name, *,
                             entry_name="access_token", allowed_hosts):
    """Attach the entry's surrogate to a urllib Request per its placement.

    - "bearer_header"            -> Authorization: Bearer <surrogate>
    - {"custom_header": name}    -> <name>: <surrogate>
    - {"query_param": ...}       -> raises: must be applied before Request
                                    creation; use url_with_surrogate_query_param()
    - {"url_path_segment": ...}  -> raises: must be applied before Request
                                    creation; use url_with_surrogate_path_segment()
    Returns the request.
    """
    ensure_allowed_url(request.full_url, allowed_hosts)
    entry = dynamic_credential_entry(credential_name, entry_name=entry_name)
    surrogate = entry["surrogate"]
    placement = entry["placement"]
    if placement == "bearer_header":
        request.add_header("Authorization", "Bearer " + surrogate)
        return request
    if isinstance(placement, dict) and len(placement) == 1:
        kind, value = next(iter(placement.items()))
        if kind == "custom_header":
            request.add_header(value, surrogate)
            return request
        if kind == "query_param":
            raise DynamicCredentialError(
                "query_param placement must be applied before Request creation; "
                "use url_with_surrogate_query_param() to build the URL first")
        if kind == "url_path_segment":
            raise DynamicCredentialError(
                "url_path_segment placement must be applied before Request creation; "
                "use url_with_surrogate_path_segment() to build the URL first")
    raise DynamicCredentialError(
        "unknown placement %r for credential %r" % (placement, credential_name))


# ---------------------------------------------------------------- responses

def read_response_body(response, chunk_size=65536):
    """Read a urllib response fully; return bytes."""
    chunks = []
    while True:
        chunk = response.read(chunk_size)
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks)


def read_json_response(response):
    """Read a urllib response fully and parse it as JSON."""
    return json.loads(read_response_body(response).decode("utf-8"))
