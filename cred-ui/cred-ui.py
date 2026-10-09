#!/usr/bin/env python3
"""
cred-ui -- localhost-only web UI for the swapd credential store.

A small page for adding, listing, and removing credentials without
touching a terminal. Writes go through the same narrow sudo writers the
`cred` CLI uses:

    sudo -u swapd /usr/local/bin/cred-store-set <name>      (value on stdin)
    sudo -u swapd /usr/local/bin/cred-registry-set ...
    sudo -u swapd /usr/local/bin/cred-store-delete <name>

Reads go through (issue #670: absolute binary paths — the sudoers
entries pin /usr/bin/cat and /usr/bin/ls, and a bare `cat`/`ls` only
matches them when the deploy target's secure_path resolves to the same
path, a property of the deploy target, not of this repo):

    sudo -n -u swapd /usr/bin/cat /home/swapd/credentials.json
    sudo -n -u swapd /usr/bin/ls /home/swapd/secrets

Security properties (keep them if you touch this file):

  - Binds 127.0.0.1 only. Reach it over an SSH tunnel; never expose it
    on a public interface.
  - NEVER returns a secret value in any response. The list endpoint
    returns names, placements, hosts, and a has_value flag only.
  - The set endpoint never logs the request body or the value.
  - Name/host/entry values are validated against strict regexes before
    they reach subprocess argv. No shell is used anywhere.
  - Every response carries Cache-Control: no-store.
  - CSRF: the Host header must be this UI's own address, and POSTs must
    carry the X-Cred-UI: 1 header (index.html sends it on every POST).
  - API token (issues #86, #964): every /api/* endpoint additionally requires a
    per-install bearer token (Authorization: Bearer ...) that only the
    human knows — generated once into /home/swapd/ui-token (0600,
    swapd-owned), fetched at startup through a pinned sudo reader, pasted
    into the browser once per session. Any local process can set
    X-Cred-UI: 1, so the header alone authenticated nothing; the token
    closes the loopback-any-process hole down to the service's own user
    (a same-uid process can still reach it through the pinned sudo
    entries — see the honest residual in the token block below).

Stdlib only.
"""

import hmac
import json
import os
import re
import secrets
import stat
import subprocess
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler

# --- spark-vm version stamping (docs/VERSIONING.md) ---
# Single-source repo VERSION: reported at startup and on /api/version.
# Best-effort — a missing/invalid VERSION must never break startup.
_SV_HERE = os.path.dirname(os.path.abspath(__file__))
_SV_CAND = os.path.normpath(os.path.join(_SV_HERE, "..", "scripts"))
# Gate the sys.path decision on the helper cred-ui actually needs (a hard
# requirement), not on the best-effort version stamp. The install dir
# (issue #85) is self-contained — its own helpers ship flat next to
# cred-ui.py — so _SV_HERE wins when it carries the helper; otherwise the
# checkout layout's ../scripts is used. A missing helper is a broken
# install and must fail at startup, not silently fall back to the
# unbounded server: the import below stays unconditional and loud.
if os.path.isfile(os.path.join(_SV_HERE, "bounded_http.py")):
    if _SV_HERE not in sys.path:
        sys.path.insert(0, _SV_HERE)
elif os.path.isfile(os.path.join(_SV_CAND, "bounded_http.py")):
    if _SV_CAND not in sys.path:
        sys.path.insert(0, _SV_CAND)
elif _SV_HERE not in sys.path:
    sys.path.insert(0, _SV_HERE)
# Issue #471: the bounded pool + handshake-deferral server promoted out
# of confirmd (#77 M8) into scripts/bounded_http.py. scripts/ is on
# sys.path by the stamping block above; the import is unconditional —
# a missing helper is a broken checkout and must fail loud, not
# silently fall back to the unbounded server.
from bounded_http import BoundedThreadingHTTPServer
# --- credvalidate: single-source validation contract (issue #706) ---
# The name/entry/host contract lives in credlib/credvalidate.py. The
# install dir (issue #85) is self-contained — cred-ui/install.sh stages
# credvalidate.py flat next to cred-ui.py — so _CV_HERE wins when it
# carries the module; otherwise the checkout layout's ../credlib is used.
# A missing module is a broken install and must fail at startup, not
# silently run with a stale or absent contract: the import below stays
# unconditional and loud (same discipline as bounded_http above).
_CV_HERE = os.path.dirname(os.path.abspath(__file__))
_CV_CAND = os.path.normpath(os.path.join(_CV_HERE, "..", "credlib"))
if os.path.isfile(os.path.join(_CV_HERE, "credvalidate.py")):
    if _CV_HERE not in sys.path:
        sys.path.insert(0, _CV_HERE)
elif os.path.isfile(os.path.join(_CV_CAND, "credvalidate.py")):
    if _CV_CAND not in sys.path:
        sys.path.insert(0, _CV_CAND)
# Unconditional: no local fallback copies — drift died here (issue #706).
from credvalidate import (
    check_entry,
    check_host,
    check_host_legacy,
    check_name,
    check_name_legacy,
)
try:
    from sparkvm_version import sparkvm_version as _sv_fn
    SPARKVM_VERSION = _sv_fn(start=_SV_HERE)
except Exception:
    # Best-effort stamp (SyntaxError included): a broken reader or VERSION
    # must never break the component's startup.
    SPARKVM_VERSION = "0.0.0-unknown"
# --- end version stamping ---

# index.html lives next to this file. Resolve it absolutely: the old code
# relied on main()'s chdir, so any other way of starting the server
# (systemd WorkingDirectory, tests) 500'd the homepage.
_INDEX_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "index.html")

BIND = "127.0.0.1"
PORT = 18740

# CSRF hardening (same class as cua-bridge): the UI binds localhost only,
# but a browser on the user's own machine can reach it through their SSH
# tunnel. Require our own Host header on every request and a custom header
# on all POSTs, so a malicious web page can't drive the API (browsers must
# preflight custom headers; we never answer with permissive CORS).
ALLOWED_HOSTS = {"%s:%d" % (BIND, PORT), "localhost:%d" % PORT}
# NOTE: ALLOWED_HOSTS is derived from BIND/PORT above -- do not hand-edit
# the set. A hand-maintained literal drifts the day PORT changes and the
# CSRF gate then 403s everything including index.html.
CSRF_HEADER = "X-Cred-UI"
CSRF_VALUE = "1"

# --- API token auth (issues #86, #964) ---
# The CSRF gates stop malicious web pages, but any local process can set
# X-Cred-UI: 1 — the management API authenticated nothing, so any local
# process that could reach the loopback listener could add, list, remove,
# and rebind every credential. Every /api/* endpoint now additionally
# requires a per-install bearer token (issue #86's second fix option:
# "a per-install token the human pastes once"). The token is generated
# once (256 bits) and pasted into the browser once per browser session
# (sessionStorage; never a cookie, never a URL, never logged).
# `--print-token` shows it for the paste ceremony, `--rotate-token`
# replaces it (restart the service afterwards).
#
# Placement (issue #964): the token lives under swapd ownership at
# /home/swapd/ui-token (0600), fetched at startup through the pinned
# `sudo -n -u swapd /usr/bin/cat /home/swapd/ui-token` sudoers entry
# (same pattern as the registry reads) and written through the narrow
# /usr/local/bin/cred-ui-token-set writer (first start, --rotate-token).
# A same-uid process can no longer read the token straight off the
# filesystem. CRED_UI_TOKEN_FILE still names a local 0600 file instead
# (dev, CI, tests) — the old ~/.config/cred-ui/token default is gone.
#
# Honest residual: sudo matches the invoking *user*, not the process, so
# a same-uid process can still reach the token through these pinned sudo
# entries — and already holds equivalent power through the NOPASSWD
# writers (#86's own caveat). What the move ends is the silent
# direct-file-read path: every read now crosses sudo's audit trail. It
# stops other-uid local processes (including the on-box agent user, which
# can neither read the swapd-owned file nor use the service-user-scoped
# sudo entries), sandboxed agents, and containers with loopback reach. The
# hosted multi-tenancy identity question (#281) — per-tenant session auth
# tied to H11's session model — stays open.
_TOKEN_FILE_ENV = "CRED_UI_TOKEN_FILE"
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
_API_TOKEN = None  # lazy: loaded once, cached (tests reset via _reset_token_cache)

# Issue #964: absolute paths pinned exactly as the sudoers entries carry
# them (issue #670's pin; see the REGISTRY_CAT comment). No shell
# anywhere; -n so a request thread never blocks on a password prompt.
UI_TOKEN_CAT = ["sudo", "-n", "-u", "swapd", "/usr/bin/cat",
                "/home/swapd/ui-token"]
UI_TOKEN_SET = ["sudo", "-n", "-u", "swapd",
                "/usr/local/bin/cred-ui-token-set"]


def _swapd_token_backed():
    """True when the token lives under swapd ownership (the default);
    False when CRED_UI_TOKEN_FILE names a local file (dev, CI, tests)."""
    return not os.environ.get(_TOKEN_FILE_ENV)


def _token_path():
    """Local-file token path — only meaningful when CRED_UI_TOKEN_FILE
    is set (dev, CI, tests). The old ~/.config/cred-ui/token default is
    gone (issue #964); reaching this without the env var is a bug, so
    fail loud instead of guessing a path."""
    override = os.environ.get(_TOKEN_FILE_ENV)
    if not override:
        raise RuntimeError(
            "CRED_UI_TOKEN_FILE is not set and the swapd backend was "
            "bypassed — refusing to guess a token path")
    return override


def _read_token_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def _ensure_token_parent(path):
    """Create the token file's parent dir (and any missing ancestors)
    with 0700 throughout. os.makedirs only honors `mode` on the leaf —
    intermediates get 0777&~umask (0770 under umask 007) — and a
    group-writable intermediate would trip _check_token_dir_chain on the
    very next start, wedging a box we just provisioned."""
    parent = os.path.dirname(path)
    if not parent:
        return
    cur, missing = parent, []
    while not os.path.isdir(cur):
        missing.append(cur)
        nxt = os.path.dirname(cur)
        if nxt == cur:
            break
        cur = nxt
    os.makedirs(parent, mode=0o700, exist_ok=True)
    for d in missing:
        try:
            os.chmod(d, 0o700)
        except OSError:
            pass  # lost a race; the chain check below is authoritative


def _check_token_dir_chain(path):
    """Fail closed when any ancestor directory of the token file (up to,
    not including, $HOME) lets a non-owner replace the child entry — i.e.
    is group/other-writable WITHOUT the sticky bit. A writable parent
    lets a non-owner uid rename/replace the token file — or plant a
    pre-first-start symlink to a file with a known value — and walk
    straight through the management API. The file-mode check alone
    cannot see this. The sticky bit (e.g. /tmp's 1777) counts as safe:
    it restricts renames to the entry's owner regardless of the write
    bits."""
    home = os.path.expanduser("~")
    d = os.path.dirname(os.path.abspath(path))
    home_abs = os.path.abspath(home)
    while d != home_abs and d != os.path.dirname(d):
        try:
            st = os.stat(d)
        except FileNotFoundError:
            # A missing ancestor is created 0700 by the makedirs below —
            # nothing to check; keep checking the ancestors above it.
            d = os.path.dirname(d)
            continue
        except OSError as e:
            # An existing-but-unstatable ancestor fails closed rather
            # than assumed safe.
            raise RuntimeError(
                "cannot stat token dir %s (%s); refusing to start" % (d, e))
        mode = st.st_mode
        if (mode & 0o022) and not (mode & stat.S_ISVTX):
            raise RuntimeError(
                "token dir %s is replaceable by group/other (mode %o, no "
                "sticky bit); refusing to start — fix with: chmod go-w %s"
                % (d, mode & 0o7777, d))
        d = os.path.dirname(d)


def _read_swapd_token():
    """Read the token through the pinned sudo cat. Returns None when the
    file is absent (fresh box, nothing generated yet — the first-start
    path); raises RuntimeError on any other read failure — fail closed,
    never an empty guess. The absent-file match anchors on cat's
    path-specific prefix AND the errno phrase, the same fail-loud
    posture as read_registry's absent check (issue #672): a locale that
    renames the phrase fails loud, never silent. Every other
    stderr (permission denied, no sudoers entry) stays loud."""
    rc, out, err = run(UI_TOKEN_CAT)
    if rc == 0:
        return out.strip()
    if "cat: %s: No such file or directory" % UI_TOKEN_CAT[-1] in err:
        return None
    raise RuntimeError(
        "cannot read the swapd UI token (%s); refusing to start — "
        "check the sudoers entries and that proxy/deploy.sh ran"
        % err.strip()[-200:])


def _write_swapd_token(token):
    """Write the token through the narrow writer (value on stdin). The
    writer re-validates the token alphabet and writes atomically 0600
    swapd-owned; the UI's regex pre-check is fail-fast UX, not the
    enforcement — a non-zero writer exit fails closed, loudly."""
    if not _TOKEN_RE.match(token):
        raise RuntimeError("refusing to write a malformed token")
    rc, _, err = run(UI_TOKEN_SET, inp=token)
    if rc != 0:
        raise RuntimeError(
            "swapd UI token write failed: %s" % err.strip()[-200:])


def _load_or_create_swapd_token():
    """Swapd-backed variant of the token load: read via the pinned cat;
    on first start generate, write via the narrow writer, and re-read to
    prove the write landed with the exact value. Any mismatch fails
    closed — the UI trusts only what it reads back."""
    token = _read_swapd_token()
    if token is not None:
        if not _TOKEN_RE.match(token):
            raise RuntimeError(
                "swapd UI token is empty or malformed; regenerate with "
                "--rotate-token")
        return token
    fresh = secrets.token_urlsafe(32)
    _write_swapd_token(fresh)
    if _read_swapd_token() != fresh:
        raise RuntimeError(
            "swapd UI token write did not land; refusing to start")
    return fresh


def _rotate_swapd_token():
    """Replace the swapd-owned token atomically via the narrow writer,
    then prove the rotation landed by reading back. The running server
    keeps the old token cached until restart — the operator restarts
    cred-ui after rotating."""
    token = secrets.token_urlsafe(32)
    _write_swapd_token(token)
    if _read_swapd_token() != token:
        raise RuntimeError(
            "swapd UI token rotation did not land; refusing to start")
    return token


def _load_or_create_token(path=None):
    """Return the API token, generating it on first start. Fail-closed on
    a missing/unreadable/malformed token file or on a file other users
    can read — a world-readable token file would hand the authenticator
    to exactly the local processes it exists to exclude."""
    if _swapd_token_backed():
        return _load_or_create_swapd_token()
    path = path or _token_path()
    _check_token_dir_chain(path)
    try:
        st = os.stat(path)
    except FileNotFoundError:
        st = None
    except OSError as e:
        raise RuntimeError("cannot stat token file %s: %s" % (path, e))
    if st is not None:
        if st.st_mode & 0o077:
            raise RuntimeError(
                "token file %s is readable by group/other (mode %o); "
                "refusing to start — fix with: chmod 600 %s"
                % (path, st.st_mode & 0o777, path))
        try:
            token = _read_token_file(path)
        except OSError as e:
            raise RuntimeError("cannot read token file %s: %s" % (path, e))
        if not _TOKEN_RE.match(token):
            raise RuntimeError(
                "token file %s is empty or malformed; regenerate with "
                "--rotate-token" % path)
        return token
    # First start: generate, write a COMPLETE file, then link it into
    # place atomically — os.link fails with FileExistsError when the
    # target exists, so a racing first-start either links first (we read
    # the winner) or fails to link (it reads ours); nobody ever reads a
    # half-written token file. (The old O_EXCL-direct-create shape let the
    # loser stat+read the winner's file mid-write and fail closed
    # spuriously.)
    token = secrets.token_urlsafe(32)
    _ensure_token_parent(path)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(token + "\n")
        try:
            os.link(tmp, path)
        except FileExistsError:
            pass  # lost the race; the winner's file is complete
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    return _load_or_create_token(path)  # now exists, fully written


def _rotate_token(path=None):
    """Replace the token atomically (0600). The running server keeps
    the old token cached until restart — the operator restarts cred-ui
    after rotating."""
    if _swapd_token_backed():
        return _rotate_swapd_token()
    path = path or _token_path()
    token = secrets.token_urlsafe(32)
    _ensure_token_parent(path)
    _check_token_dir_chain(path)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(token + "\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return token


def _reset_token_cache():
    """Test hook: drop the cached token so the next api_token() re-reads."""
    global _API_TOKEN
    _API_TOKEN = None


def api_token():
    global _API_TOKEN
    if _API_TOKEN is None:
        _API_TOKEN = _load_or_create_token()
    return _API_TOKEN

# --- Validation contract: single-sourced from credlib/credvalidate.py ---
# (imported above; issue #706). The functions below are the UI's thin
# boolean adapters over the shared checkers — no local regexes, caps, or
# RESERVED_ENTRIES live here anymore, so this file cannot drift from the
# writer's contract again. The UI must never accept what the writer
# rejects: it previously did (ports, underscores), producing a confusing
# post-store "add-host failed" after the secret was already written.


def host_ok_legacy(h):
    # Legacy-tolerant host check for remove-host: shape only, so
    # over-long legacy bindings stay removable. Any rejection (including
    # non-string input) fail-closes to False — do_POST answers that with
    # 400 — and the shared checker raises ValueError, never TypeError, so
    # no isinstance guard is needed here anymore.
    try:
        check_host_legacy(h)
    except ValueError:
        return False
    return True


def host_ok(h):
    # Canonical host check for add-host: dotted-hostname shape (no
    # underscores, no ports — the swap addon strips ports when matching,
    # so a port in the registry would be dead config), labels capped at
    # 63 chars (DNS), whole name at 253. Same fail-closed contract as
    # host_ok_legacy above.
    try:
        check_host(h)
    except ValueError:
        return False
    return True


def name_ok_legacy(n):
    # Legacy-tolerant name check for management verbs: charset only, so
    # credentials created before the #150 caps stay manageable. Same
    # fail-closed boolean contract as the host adapters above.
    try:
        check_name_legacy(n)
    except ValueError:
        return False
    return True
HEADER_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
PARAM_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")

# -n everywhere: the sudoers entries are NOPASSWD, and a request thread
# must never block on a password prompt (matches the cred CLI).
# Absolute /usr/bin paths (issue #670): the sudoers entries are absolute
# (/usr/bin/cat, /usr/bin/ls), and a bare `cat` only matches them when
# sudo happens to resolve it through secure_path to the same path — a
# property of the deploy target, not of this repo. Sibling readers
# (credlib) already pin the path; the UI does the same.
STORE_SET = ["sudo", "-n", "-u", "swapd", "/usr/local/bin/cred-store-set"]
REGISTRY_SET = ["sudo", "-n", "-u", "swapd", "/usr/local/bin/cred-registry-set"]
REGISTRY_CAT = ["sudo", "-n", "-u", "swapd", "/usr/bin/cat", "/home/swapd/credentials.json"]
SECRETS_LS = ["sudo", "-n", "-u", "swapd", "/usr/bin/ls", "/home/swapd/secrets"]
SECRET_DELETE = ["sudo", "-n", "-u", "swapd", "/usr/local/bin/cred-store-delete"]


def run(argv, inp=None):
    # stdin is bytes on the wire: callers pass str (issue #964 exposed
    # this — subprocess.run(input=<str>) raises TypeError, which had been
    # 500ing api_set's STORE_SET call on the box). Encode UTF-8 here,
    # once, instead of at every call site.
    if isinstance(inp, str):
        inp = inp.encode("utf-8")
    p = subprocess.run(argv, input=inp, capture_output=True, timeout=15)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


class RegistryCorruptError(Exception):
    """The registry file exists and is readable but is not valid JSON (or
    not a JSON object), or the store read itself failed. Raised (not
    swallowed) so /api/creds fails loud with the generic scrubbed 500
    instead of rendering every credential as `registered: false` — the
    silent-downgrade class (#672)."""


def read_registry():
    rc, out, err = run(REGISTRY_CAT)
    if rc != 0:
        # A genuinely absent store (fresh box, nothing registered yet) is
        # the one honest-empty case; cat names it on stderr with its
        # path-specific prefix. Anchor the match on that prefix *and* the
        # errno phrase instead of the bare "No such file or directory"
        # substring: locale drift is already safe-biased to loud, and the
        # anchor rules out false positives from other tools' stderr naming
        # the same phrase — while other errors on THIS path (permission
        # denied, is-a-directory) stay loud (#672), never silent {}.
        if "cat: %s: No such file or directory" % REGISTRY_CAT[-1] in err:
            return {}
        raise RegistryCorruptError("registry read failed")
    try:
        reg = json.loads(out)
    except ValueError:
        raise RegistryCorruptError("registry is not valid JSON")
    if not isinstance(reg, dict):
        raise RegistryCorruptError("registry is not a JSON object")
    return reg


def list_secret_names():
    rc, out, _ = run(SECRETS_LS)
    if rc != 0:
        return set()
    # Legacy-tolerant filter (charset only): a pre-#150 long name still has
    # a real value on disk, and the /api/creds `has_value` flag must say
    # so. The canonical NAME_RE filter here used to drop such names, so a
    # credential `cred get` could read showed has_value=false in the UI
    # (2026-09-23 arch deep-read finding).
    return {n for n in out.split() if name_ok_legacy(n)}


def snapshot():
    reg = read_registry()
    have = list_secret_names()
    creds = []
    for name in sorted(set(reg) | have):
        entry = reg.get(name, {}) if isinstance(reg.get(name), dict) else {}
        hosts = entry.get("allowed_hosts", [])
        # Render only the placement of each entry. Registry entry dicts may
        # gain keys over time (scrub flags, grant metadata); an allowlist
        # keeps a future secret-adjacent field from leaking into /api/creds.
        placements = {
            k: v["placement"] for k, v in entry.items()
            if k != "allowed_hosts" and isinstance(v, dict) and "placement" in v
        }
        creds.append({
            "name": name,
            "has_value": name in have,
            "registered": name in reg,
            "allowed_hosts": hosts if isinstance(hosts, list) else [],
            "entries": placements,
        })
    return {"creds": creds}


def placement_json(kind, arg):
    # The bare kinds take no argument: the UI hides the arg field for them,
    # so a non-empty arg here is a hand-built request, not a UI flow — reject
    # it loudly rather than silently dropping the user's input. (Canonical
    # placement contract shared with the `cred` CLI and
    # proxy/cred-registry-set, #150.)
    if kind in ("bearer_header", "url_path_segment"):
        if arg:
            raise ValueError("placement takes no argument")
        return json.dumps(kind)
    if kind == "custom_header":
        # #118: a non-string arg from a hand-built request used to escape as
        # a TypeError from re.match and drop the connection instead of a
        # clean 400. Non-strings are bad input, same as a bad string shape.
        if not isinstance(arg, str) or not HEADER_RE.match(arg):
            raise ValueError("bad header name")
        return json.dumps({"custom_header": arg})
    if kind == "query_param":
        if not isinstance(arg, str) or not PARAM_RE.match(arg):
            raise ValueError("bad query param name")
        return json.dumps({"query_param": arg})
    raise ValueError("unknown placement")


class Handler(BaseHTTPRequestHandler):
    server_version = "cred-ui/1.0"

    # Issue #282: per-connection socket timeout. StreamRequestHandler
    # applies this to the connection socket in setup(), so a client
    # that stalls mid-headers or mid-body (a read with no bytes for
    # 10 s) releases its handler thread instead of pinning it forever.
    # This is a per-read idle bound, not a total deadline: a client
    # that dribbles just under the timeout per read can still hold a
    # thread (accepted residual — the UI binds 127.0.0.1 only, so only
    # a local attacker could exploit it, and such an attacker has
    # cheaper DoS paths). 10 s is generous for localhost traffic and
    # mirrors the timeout discipline of the subprocess (15 s) and
    # credlib registry (10 s) paths.
    timeout = 10

    def log_message(self, fmt, *args):  # quieter logs; never log bodies
        pass

    def _send(self, code, obj, ctype="application/json"):
        body = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        # Response hardening (issue #281 re-sweep): the management UI
        # previously sent none of these. X-Frame-Options DENY keeps any
        # other localhost page from framing the unlock/delete flows
        # (clickjacking an operator's session); nosniff stops MIME
        # sniffing of the JSON API; no-referrer keeps the page from
        # leaking its origin on any future outbound navigation. Nothing
        # frames cred-ui legitimately, so DENY is safe on every route,
        # including the public index and version endpoints.
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        try:
            n = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            n = 0
        if n <= 0 or n > 1_000_000:
            return None
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except (OSError, ValueError):
            # OSError covers socket.timeout from the Handler.timeout
            # bound above (socket.timeout IS TimeoutError): a stalled
            # body read degrades to a 400 via the None contract instead
            # of pinning the handler thread.
            return None

    def _csrf_ok(self):
        host = (self.headers.get("Host") or "").split(",")[0].strip().lower()
        if host not in ALLOWED_HOSTS:
            return False
        if self.command in ("POST", "PUT", "DELETE"):
            return self.headers.get(CSRF_HEADER) == CSRF_VALUE
        return True

    def _check_csrf(self):
        if not self._csrf_ok():
            self._send(403, {"error": "forbidden"})
            return False
        return True

    def _auth_ok(self):
        # Per-install bearer token (issue #86). Exact "Bearer <token>"
        # shape; anything else (missing, basic, trailing junk) is
        # unauthenticated. compare_digest over the presented credential
        # keeps the comparison timing-safe.
        auth = self.headers.get("Authorization") or ""
        if not auth.startswith("Bearer "):
            return False
        try:
            return hmac.compare_digest(auth[len("Bearer "):], api_token())
        except Exception:  # noqa: BLE001 -- fail closed, never 500 on auth
            return False

    def _check_auth(self):
        # 401, deliberately without WWW-Authenticate: a browser basic-auth
        # popup would be the wrong ceremony (the token is pasted, not
        # typed into a dialog), and JSON keeps the UI's error path.
        if not self._auth_ok():
            self._send(401, {"error": "unauthorized"})
            return False
        return True

    def do_GET(self):
        if not self._check_csrf():
            return
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/api/") and path != "/api/version":
            # /api/version is public (service name + version only);
            # index.html must stay public too (the human needs it to
            # paste the token). Everything else under /api/ is the
            # management API: /api/creds lists names, placements, and
            # hosts — recon for a local attacker — so it is gated like
            # the state-changing endpoints.
            if not self._check_auth():
                return
        if path == "/":
            try:
                with open(_INDEX_PATH, "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            except OSError:
                self._send(500, {"error": "index.html missing"})
        elif path == "/api/creds":
            try:
                self._send(200, snapshot())
            except Exception:  # noqa: BLE001
                # Deliberately generic: interpolating the exception here
                # would disclose local paths on a read failure.
                self._send(500, {"error": "read failed"})
        elif path == "/api/version":
            self._send(200, {"service": "cred-ui", "version": SPARKVM_VERSION})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._check_csrf():
            return
        # Auth before the body read: an unauthenticated client must not
        # make us read (or time out on) a request body.
        if not self._check_auth():
            return
        path = urllib.parse.urlparse(self.path).path
        data = self._read_json()
        if data is None:
            self._send(400, {"error": "bad JSON body"})
            return
        try:
            if path == "/api/set":
                self._send(200, api_set(data))
            elif path == "/api/delete":
                self._send(200, api_delete(data))
            elif path == "/api/host/add":
                self._send(200, api_host(data, add=True))
            elif path == "/api/host/remove":
                self._send(200, api_host(data, add=False))
            else:
                self._send(404, {"error": "not found"})
        except ValueError as e:
            self._send(400, {"error": str(e)})
        except RuntimeError as e:
            self._send(500, {"error": str(e)})


# The swapd writer refuses values over 64 KiB (cred-store-set:
# max_bytes=65536). The UI must enforce the same bound on the *bytes* it
# sends — never the decoded characters — before invoking the writer, the
# same frontend/writer agreement the `cred` CLI holds (#149): 64 KiB of
# 4-byte UTF-8 is only 16 Ki characters, so a character cap would let
# multi-megabyte input through. Today the writer refuses late with a
# 500; refuse early with a 400, before the sudo spawn.
SECRET_MAX_BYTES = 65536


def api_set(data):
    name = data.get("name", "")
    value = data.get("value", "")
    entry = data.get("entry", "access_token") or "access_token"
    kind = data.get("placement", "bearer_header")
    arg = data.get("placement_arg", "")
    hosts = data.get("hosts", []) or []

    try:
        check_name(name)
    except ValueError:
        raise ValueError("bad credential name (use [A-Za-z0-9_-], max 64 chars)")
    try:
        check_entry(entry)
    except ValueError:
        raise ValueError("bad entry name")
    if not isinstance(value, str):
        raise ValueError("empty secret value")
    # Strip at most one trailing newline -- pastes from password managers
    # and textareas commonly include one. (rstrip would silently alter a
    # secret that legitimately ends in several newlines.) The lone-\r
    # branch covers classic-Mac-style pastes (#710): without it a "\r"-only
    # paste was truthy pre-chomp, stored a literal "\r" as the secret, and
    # never reached the emptiness check below.
    if value.endswith("\r\n"):
        value = value[:-2]
    elif value.endswith("\n"):
        value = value[:-1]
    elif value.endswith("\r"):
        value = value[:-1]
    # Emptiness is checked AFTER the chomp (#708): a "\n"-only paste is
    # truthy pre-chomp, chomps to "", and would otherwise sail past this
    # check and hit the writer's empty-refusal late as a 500 instead of
    # the clean 400 the UI owes for empty input.
    if not value:
        raise ValueError("empty secret value")
    if not isinstance(hosts, list) or not all(host_ok(h) for h in hosts):
        raise ValueError("bad host (use a hostname: letters, digits, "
                         "hyphens, dots; no underscores, no ports)")
    pjson = placement_json(kind, arg)

    secret = value.encode("utf-8")
    if len(secret) > SECRET_MAX_BYTES:
        # #149 parity with the `cred` CLI: the writer refuses >64 KiB, so
        # the UI must refuse up front with a clean 400 rather than
        # spawning sudo and 500ing on the writer's refusal. Byte cap,
        # not character cap (see SECRET_MAX_BYTES), checked after the
        # one-newline chomp above, so stored bytes == intended value.
        raise ValueError("secret exceeds 64 KiB \u2014 refusing before invoking the writer")

    rc, _, err = run(STORE_SET + [name], inp=secret)
    if rc != 0:
        raise RuntimeError("store failed: %s" % err.strip()[-200:])
    # Atomic register + host binding (#116): one writer call, so a
    # mid-loop writer failure can never leave the credential registered
    # with only a prefix of its intended hosts.
    rc, _, err = run(REGISTRY_SET + ["set-with-hosts", name, entry, pjson] + hosts)
    if rc != 0:
        raise RuntimeError("register failed (secret IS stored): %s" % err.strip()[-200:])
    return {"ok": True, "name": name}


def api_delete(data):
    name = data.get("name", "")
    # Management path: legacy names stay deletable.
    if not name_ok_legacy(name):
        raise ValueError("bad credential name")
    # Remove the stored value first (the wrapper ignores "no such file" --
    # the registry may exist alone). A real failure must surface: deleting
    # the registry while the value survives would report success with the
    # secret still on disk (and a later re-registration would silently
    # resurrect the stale value).
    rc, _, err = run(SECRET_DELETE + [name])
    if rc != 0:
        raise RuntimeError("store delete failed: %s" % err.strip()[-200:])
    rc, _, err = run(REGISTRY_SET + ["remove", name])
    if rc != 0 and "not registered" not in err:
        raise RuntimeError("unregister failed: %s" % err.strip()[-200:])
    return {"ok": True, "name": name}


def api_host(data, add):
    name = data.get("name", "")
    host = data.get("host", "")
    # Management path: legacy names stay manageable. New bindings are
    # always canonical; removing a legacy over-long binding stays possible.
    if not name_ok_legacy(name):
        raise ValueError("bad credential name")
    host_okay = host_ok(host) if add else host_ok_legacy(host)
    if not host_okay:
        raise ValueError("bad host (use a hostname: letters, digits, "
                         "hyphens, dots; no underscores, no ports)")
    rc, _, err = run(REGISTRY_SET + ["add-host" if add else "remove-host", name, host])
    if rc != 0:
        raise RuntimeError("host update failed: %s" % err.strip()[-200:])
    return {"ok": True}


def main():
    import os
    if "--print-token" in sys.argv[1:]:
        # The paste ceremony: shows the per-install API token once so the
        # human can paste it into the browser. Run on the box; never log
        # it, never send it anywhere but the browser's sessionStorage.
        print(api_token(), flush=True)
        return
    if "--rotate-token" in sys.argv[1:]:
        _rotate_token()
        _reset_token_cache()
        print("token rotated; restart cred-ui for the new token to take "
              "effect", flush=True)
        return
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    # Fail fast at startup (not on the first request) if the token file
    # is missing-and-uncreatable, unreadable, or malformed.
    api_token()
    # Issue #471: bounded thread pool — ThreadingHTTPServer spawns one
    # thread per connection, so a local peer slow-lorising the UI could
    # grow the pool without bound. Over-cap connections are closed
    # immediately (fail closed), never queued. Handler.timeout = 10
    # (issue #282) already bounds each socket read; no TLS here, so the
    # handshake-deferral half of the helper is inert.
    srv = BoundedThreadingHTTPServer((BIND, PORT), Handler)
    print("cred-ui listening on http://%s:%d (localhost only)" % (BIND, PORT), flush=True)
    print("cred-ui version=%s" % SPARKVM_VERSION, flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
