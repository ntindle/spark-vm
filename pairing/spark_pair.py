#!/usr/bin/env python3
"""spark-pair: pairing-code box enrollment client for the spark-vm control plane.

Implements issue #844's box side and the human-approval side:

  Box (no inbound ports; everything is outbound HTTPS to the control plane):
    spark-pair.py init                      # generate ed25519 keypair locally
    spark-pair.py request --name mybox       # ask control plane for a code
    spark-pair.py redeem                     # wait for approval, prove key
                                             # possession, save the box token
    spark-pair.py heartbeat                  # send one liveness heartbeat to
                                             # the control plane (cron ~1/min)

  Owner (any machine; needs an owner API key):
    spark-pair.py approve --pairing-id <id>  # verify fingerprint, approve
    spark-pair.py revoke --box-id <id>       # revoke a box token immediately

  Box token rotation (issue #846):
    spark-pair.py rotate                     # new short-lived token, proof of
                                             # possession (ed25519 signature)
    spark-pair.py rotate --auto              # cron-friendly: rotate only when
                                             # the token expires within 6 h

  Durable-command ingest (issue #874):
    spark-pair.py ingest                     # pull plane commands
                                             # (GET /v1/boxes/{id}/commands/
                                             # pending), ack them, and stamp
                                             # approval_decision commands into
                                             # confirmd's answered/consumed
                                             # store (cron ~1/min)

The private key never leaves the box. The pairing code expires (15 min).
The bearer token issued at redeem is short-lived (24 h); `rotate` replaces
it before expiry so heartbeats never drop. The server half of rotation
(POST /v1/boxes/token/rotate, POST /v1/boxes/{id}/revoke) is specified in
pairing/README.md; this client implements that contract. The plane update
implementing the endpoints is still pending — `rotate`/`revoke` report
that honestly instead of failing opaquely.

Stdlib only. State lives in ~/.config/spark-pair (override with --dir or
SVM_PAIR_DIR). Key/token files are written mode 0600. Nothing secret is
ever printed.
"""
import argparse
import base64
import fcntl
import getpass
import ipaddress
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.error

import ed25519

DEFAULT_CONTROL = "https://api.sparkvm.dev"
USER_AGENT = "spark-pair/1"
POLL_INTERVAL = 5


def _state_dir(args):
    d = args.dir or os.environ.get("SVM_PAIR_DIR") or os.path.expanduser(
        "~/.config/spark-pair")
    os.makedirs(d, mode=0o700, exist_ok=True)
    return d


def _write_private(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        # 0600 at creation is not enough: a pre-existing file keeps its
        # wider mode through the write. Force it every time.
        os.fchmod(fd, 0o600)
        os.write(fd, data)
    finally:
        os.close(fd)


def _read_json_file(path):
    with open(path) as f:
        return json.load(f)


# Marker _http sets on the *synthesized* 404 fallback payload only: the
# plane answered 404 with no JSON body at all, i.e. the endpoint is not
# implemented yet. The "endpoint not implemented" classification keys on
# this marker — never on the "http=404" error string, which a JSON plane
# can legitimately return for some *other* failure (#882).
_TRANSPORT_404 = "_transport_404"


def _plane_missing(resp):
    """True when resp is _http's synthesized 404 fallback (the control
    plane has no JSON body at this path). A hostile or buggy plane cannot
    forge it: _http strips the marker from plane-returned bodies and sets
    it only on the payloads it synthesizes itself. One predicate for all
    three call sites (rotate/revoke/heartbeat), so the classification rule
    lands once (#880, #882)."""
    return isinstance(resp, dict) and resp.get(_TRANSPORT_404) is True


def _http(method, url, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    hdrs = {"User-Agent": USER_AGENT, **(headers or {})}
    if data is not None:
        # Content-Type describes the body; a bodyless GET must not claim one.
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    try:
        with _HTTP_OPENER.open(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode())
            if not isinstance(payload, dict):
                # A 2xx with a non-object body cannot carry the plane's
                # contract; every call site assumes dict, so normalize here
                # instead of guarding at each site (the heartbeat path's
                # bespoke non-dict guard stays as defense in depth for
                # callers that bypass _http, e.g. tests).
                return resp.status, {
                    "ok": False,
                    "error": "malformed plane response (non-object body)"}
            # A hostile plane cannot smuggle the fallback marker into a
            # 2xx body either: only _http may set it, and it never does
            # here. Strip it to keep that invariant global.
            payload.pop(_TRANSPORT_404, None)
            return resp.status, payload
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode())
        except Exception:
            payload = None  # not a JSON body at all
        if not isinstance(payload, dict):
            # Mirror the 2xx normalization above: a JSON list/string/null
            # error body would otherwise AttributeError at the first
            # resp.get(). Keep the http=NNN marker so the 404
            # endpoint-detection (rotate/revoke/heartbeat) keeps working.
            payload = {"ok": False, "error": f"http={e.code}"}
            if e.code == 404:
                # Mark the synthesized fallback (#882): the "endpoint not
                # implemented" classification keys on this marker, not on
                # the error string, which a JSON plane can legitimately
                # return for some other failure.
                payload[_TRANSPORT_404] = True
        else:
            # A hostile or buggy plane must not be able to forge the
            # fallback marker: strip it from plane-returned bodies, so
            # _plane_missing only ever fires on payloads _http synthesized
            # itself.
            payload.pop(_TRANSPORT_404, None)
        return e.code, payload
    except Exception as e:  # network down, DNS, TLS...
        return 0, {"ok": False, "error": f"transport: {e}"}


class _InsecureRedirectRefused(Exception):
    """The plane (or something shaping its responses) asked for a
    https->http downgrade redirect. Authorization is stripped at the new
    origin, but the request would still talk cleartext to it — bearer
    tokens and owner keys must never travel in the clear. Raised from the
    redirect handler; _http reports it as a transport failure, never a
    traceback (#885)."""


class _BadRedirectTarget(Exception):
    """A redirect target the client cannot parse (e.g. a garbage port in
    the Location header). Fail closed with a clean error class instead of
    a ValueError traceback (#885)."""


def _scrub_url_userinfo(url):
    """Remove embedded credentials (user:pass@) from a URL before it is
    echoed into error messages or logs (#885). A control URL carrying
    userinfo would otherwise leak into stdout / heartbeat.log through the
    cleartext-refusal message; the same holds for a hostile plane's
    Location header echoed in the downgrade refusal.

    Total: never raises. An unparseable URL (e.g. an unmatched IPv6
    bracket, which makes urlparse itself raise ValueError) falls back to
    a crude last-@ cut — the credentials are still gone, and the URL is
    refused on other grounds."""
    try:
        u = urllib.parse.urlparse(url)
    except ValueError:
        return url.rsplit("@", 1)[-1]
    if "@" not in u.netloc:
        return url
    try:
        host = u.hostname or ""
        port = f":{u.port}" if u.port else ""
        if ":" in host:  # IPv6 literal: urlparse strips the brackets
            host = f"[{host}]"
        netloc = host + port
    except ValueError:
        # Garbage port: crude cut still removes the credentials; the URL
        # is unusable anyway and refused on other grounds.
        netloc = u.netloc.rsplit("@", 1)[1]
    return urllib.parse.urlunparse(
        (u.scheme, netloc, u.path, u.params, u.query, u.fragment))


class _RedirectAuthStripper(urllib.request.HTTPRedirectHandler):
    """urllib forwards manually-set Authorization headers across redirects —
    including to a DIFFERENT origin. On this credential-bearing client that
    is a token leak (box bearer token, owner API key): a compromised or
    misconfigured plane, or a redirect chain the box didn't expect, would
    harvest them. Strip Authorization whenever the redirect leaves the
    original origin (scheme/host/port); same-origin redirects keep it.

    A https->http downgrade redirect is refused outright: the header strip
    is safe, but the follow-up request would talk cleartext to the new
    origin — credentials in the clear either way. Unparseable redirect
    targets (e.g. a garbage port in the Location header) fail closed with
    a clean error instead of a ValueError traceback."""

    @staticmethod
    def _origin(parsed):
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        return (parsed.scheme, (parsed.hostname or "").lower(), port)

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        try:
            old_parsed = urllib.parse.urlparse(req.full_url)
            new_parsed = urllib.parse.urlparse(
                urllib.parse.urljoin(req.full_url, newurl))
            old_origin = self._origin(old_parsed)
            new_origin = self._origin(new_parsed)
        except ValueError as e:
            # A garbage port (or other unparseable component) in the
            # request URL or the Location header: fail closed, clean.
            # Scrub before echoing: the raw Location may carry userinfo
            # the plane wants echoed back into our logs (B1); the scrub
            # is total, so it cannot raise here.
            raise _BadRedirectTarget(
                f"refusing redirect with unparseable target "
                f"{_scrub_url_userinfo(newurl)!r}: {e}")
        if old_parsed.scheme == "https" and new_parsed.scheme == "http":
            # Downgrade: the Authorization strip at the new origin is not
            # enough — the request itself would go out in the clear.
            # Scrub the target before echoing: a hostile plane's Location
            # may carry userinfo it wants echoed back into our logs.
            raise _InsecureRedirectRefused(
                "refusing https->http downgrade redirect to "
                f"{_scrub_url_userinfo(new_parsed.geturl())} — credentials "
                "would travel in the clear")
        new_req = super().redirect_request(req, fp, code, msg, headers,
                                           newurl)
        if new_req is not None and new_origin != old_origin:
            new_req.remove_header("Authorization")
        return new_req


# The client-wide opener: same as the default plus the cross-origin
# credential-strip above. urlopen's default opener is NOT used on purpose.
_HTTP_OPENER = urllib.request.build_opener(_RedirectAuthStripper)


def _check_control_url(control):
    """Fail closed on cleartext control planes.

    Bearer tokens and owner API keys travel in Authorization headers; an
    http:// control URL would send them in the clear. Loopback hosts stay
    allowed (local dev, loop-VM testing); any other http:// host needs
    explicit opt-in via SVM_PAIR_ALLOW_HTTP=1.
    Returns (ok, message)."""
    u = urllib.parse.urlparse(control)
    if u.scheme == "https":
        return True, ""
    if u.scheme != "http":
        return False, f"control URL scheme must be https (got {u.scheme!r})"
    host = (u.hostname or "").lower()
    if host == "localhost":
        return True, ""
    try:
        # A real loopback test: "127.evil.com".startswith("127.") is True,
        # but it is a public DNS name, not loopback — never trust the
        # prefix. (Note: "127.1" shorthand raises ValueError in ipaddress
        # and is therefore refused — same as the old prefix test; no
        # behavior change.)
        if ipaddress.ip_address(host).is_loopback:
            return True, ""
    except ValueError:
        pass  # not an IP literal: fall through to the refusal below
    if os.environ.get("SVM_PAIR_ALLOW_HTTP") == "1":
        return True, ""
    # Scrub before echoing: a control URL with embedded user:pass@ would
    # otherwise leak the credentials into stdout / heartbeat.log (#885).
    return False, (f"refusing cleartext http:// control plane "
                   f"({_scrub_url_userinfo(control)}) — "
                   "bearer tokens and owner keys would travel in the clear "
                   "(use https://, a loopback host, or SVM_PAIR_ALLOW_HTTP=1)")


def _resolve_control(args, stored=None):
    """Resolve the control URL (argv > stored file > env > default) and fail
    closed on cleartext. Returns (control, "") or (None, msg): the caller
    reports msg its own way (print vs _fail) and returns 1. A single
    resolution path, so a new command cannot forget the cleartext check."""
    control = (args.control or (stored.get("control") if stored else None)
               or os.environ.get("SVM_CONTROL") or DEFAULT_CONTROL)
    ok, msg = _check_control_url(control)
    return (control, "") if ok else (None, msg)


def _key_paths(d):
    return (os.path.join(d, "box.key"), os.path.join(d, "box.pub"))


def cmd_init(args):
    key_path, pub_path = _key_paths(_state_dir(args))
    if os.path.exists(key_path) and not args.force:
        print(f"key already exists at {key_path} (use --force to replace)")
        return 1
    seed, pub = ed25519.generate_keypair()
    _write_private(key_path, base64.b64encode(seed))
    with open(pub_path, "w") as f:
        f.write(base64.b64encode(pub).decode())
    print(f"keypair written to {key_path} (0600) + {pub_path}")
    print()
    print("Box key fingerprint — the owner must verify this at approval:")
    print("  " + ed25519.fingerprint(pub))
    return 0


def cmd_request(args):
    d = _state_dir(args)
    key_path, pub_path = _key_paths(d)
    if not os.path.exists(key_path):
        print("no keypair yet — run `spark-pair.py init` first")
        return 1
    seed = base64.b64decode(open(key_path, "rb").read())
    pub = base64.b64decode(open(pub_path).read())
    if ed25519.publickey_from_seed(seed) != pub:
        print("key/pub mismatch — refusing to request (re-run init --force)")
        return 1
    control, msg = _resolve_control(args)
    if control is None:
        print(msg)
        return 1
    status, resp = _http("POST", control.rstrip("/") + "/v1/pairing/request",
                         {"name": args.name,
                          "pubkey": base64.b64encode(pub).decode(),
                          "fingerprint": ed25519.fingerprint(pub)})
    if status != 201 or not resp.get("ok"):
        print(f"request failed: {_plane_error(resp, status)}")
        return 1
    # The single-use code lives here until redeem: 0600 like the key.
    _write_private(os.path.join(d, "pairing.json"),
                   json.dumps({"pairing_id": resp["pairing_id"],
                               "code": resp["code"],
                               "expires_at": resp["expires_at"],
                               "control": control}, indent=2).encode())
    mins = max(1, int((resp["expires_at"] - time.time()) // 60))
    print()
    print("  Give this pairing code to the box owner:")
    print()
    print(f"    {_plane_text(resp['code'])}")
    print()
    print("  And confirm the key fingerprint matches what the box shows:")
    print(f"    {ed25519.fingerprint(pub)}")
    print()
    print(f"  Code expires in ~{mins} min. Then run: spark-pair.py redeem")
    return 0


def cmd_redeem(args):
    d = _state_dir(args)
    key_path, _ = _key_paths(d)
    pairing_path = os.path.join(d, "pairing.json")
    if not os.path.exists(key_path) or not os.path.exists(pairing_path):
        print("need `init` + `request` first")
        return 1
    seed = base64.b64decode(open(key_path, "rb").read())
    try:
        pairing = _read_json_file(pairing_path)
    except (OSError, ValueError) as e:
        # Corrupt state file: the same clean failure the enrollment
        # paths give, not a traceback.
        print(f"pairing.json is unreadable ({e}) — run `request` again "
              "for a fresh code")
        return 1
    if not isinstance(pairing, dict):
        # Valid JSON but not an object (a list, string, null): ["pairing_id"]
        # below would TypeError with a bare traceback — same loud failure
        # the enrollment paths got, applied to pairing.json too.
        print("pairing.json is not an object — run `request` again for a "
              "fresh code")
        return 1
    control, msg = _resolve_control(args, pairing)
    if control is None:
        print(msg)
        return 1
    pid = pairing.get("pairing_id")
    deadline = pairing.get("expires_at")
    if (not pid or not isinstance(deadline, (int, float))
            or isinstance(deadline, bool)):
        print("pairing.json is corrupt or incomplete — run `request` again "
              "for a fresh code")
        return 1
    base = control.rstrip("/") + f"/v1/pairing/{pid}"

    print("Waiting for owner approval (Ctrl-C to stop, re-run to resume)...")
    challenge = None
    while True:
        if time.time() > deadline:
            print("pairing expired — run `request` again for a fresh code")
            return 1
        status, resp = _http("GET", base + "/status")
        if status == 410 or resp.get("status") in ("expired", "consumed"):
            print(f"pairing {_plane_text(resp.get('status', 'gone'))} — run `request` again")
            return 1
        if status != 200 or not resp.get("ok"):
            print(f"status check failed: {_plane_error(resp, status)}")
            return 1
        if resp.get("status") == "approved" and resp.get("challenge"):
            challenge = resp["challenge"]
            break
        time.sleep(POLL_INTERVAL)

    # Prove possession: sign the server-issued challenge with the box key.
    sig = ed25519.sign(seed, base64.b64decode(challenge))
    status, resp = _http("POST", base + "/redeem",
                         {"signature": base64.b64encode(sig).decode()})
    if status != 201 or not resp.get("ok"):
        print(f"redeem failed: {_plane_error(resp, status)}")
        return 1
    enroll_path = os.path.join(d, "enrollment.json")
    _write_private(enroll_path, json.dumps(
        {"box_id": resp["box_id"], "token": resp["token"],
         "token_expires_at": resp["token_expires_at"],
         "control": control}, indent=2).encode())
    os.remove(pairing_path)
    print(f"enrolled as {_plane_text(resp['box_id'])} — token saved to {enroll_path} (0600)")
    exp = time.strftime("%Y-%m-%d %H:%M %Z",
                        time.localtime(resp["token_expires_at"]))
    print(f"token expires {exp} (rotate before then: spark-pair.py rotate --auto)")
    return 0


def _owner_key(args):
    key = args.owner_key or os.environ.get("SVM_OWNER_KEY")
    if not key:
        try:
            key = getpass.getpass("Owner API key: ").strip()
        except EOFError:
            key = ""  # no tty and no env/argv key: fall through to the error
    if not key:
        print("owner API key required (SVM_OWNER_KEY or --owner-key)")
        sys.exit(1)
    return key


# ---- #846: token rotation -------------------------------------------------
# Signature message: b"spark-rotate-v1|<box_id>|<window>" where window =
# floor(now/300). The server accepts the current window ± 1 (clock skew +
# in-flight requests) and verifies the signature against the box's stored
# pubkey — proof of possession, so a stolen Bearer <redacted> alone cannot rotate
# the box out. The server rotates atomically (old token dies on success)
# and keeps the previous token valid for a short grace so a box that
# crashes between the POST and the local save is not locked out.

ROTATE_WINDOW = 300
AUTO_ROTATE_WITHIN = 6 * 3600  # --auto rotates when expiry is this near
# #846's short-lived-token goal, client-enforced: the plane mints 24 h
# tokens; anything beyond 48 h is a misconfigured plane, not a token.
MAX_TOKEN_LIFETIME = 48 * 3600


def _rotate_message(box_id, window):
    return f"spark-rotate-v1|{box_id}|{window}".encode()


def cmd_rotate(args):
    d = _state_dir(args)
    key_path, _ = _key_paths(d)
    enroll_path = os.path.join(d, "enrollment.json")
    if not os.path.exists(enroll_path):
        print("not enrolled yet — run `spark-pair.py init`, `request`, `redeem` first")
        return 1
    try:
        enroll = _read_json_file(enroll_path)
    except (OSError, ValueError) as e:
        # The --auto cron path must never die with a traceback on a
        # corrupted state file.
        print(f"enrollment.json is unreadable ({e}) — re-run `redeem`")
        return 1
    box_id, token = enroll.get("box_id"), enroll.get("token")
    if not box_id or not token:
        print("enrollment.json is missing box_id/token — re-run `redeem`")
        return 1
    expires_at = enroll.get("token_expires_at")  # None = grandfathered
    if not isinstance(expires_at, int) or isinstance(expires_at, bool):
        # Corrupt/legacy expiry: treat like grandfathered (unknown bound)
        # so --auto rotates now instead of crashing on the arithmetic.
        expires_at = None
    control, msg = _resolve_control(args, enroll)
    if control is None:
        print(msg)
        return 1
    now = int(time.time())
    if args.auto:
        # Cron-friendly: stay quiet unless the token is actually near expiry.
        # Grandfathered tokens (no expiry) always rotate: they are the
        # unbounded-lifetime case #846 exists to eliminate.
        if expires_at is not None and expires_at - now > args.within:
            return 0
    sig_b64 = None
    if os.path.exists(key_path):
        try:
            seed = base64.b64decode(open(key_path, "rb").read())
        except (OSError, ValueError) as e:
            print(f"box.key is unreadable ({e}) — re-run `init --force` "
                  "and re-pair the box")
            return 1
        sig = ed25519.sign(seed, _rotate_message(box_id, now // ROTATE_WINDOW))
        sig_b64 = base64.b64encode(sig).decode()
    # Serialize the network call + the save under a lock: a manual `rotate`
    # racing the --auto cron job could otherwise leave a dead token on disk
    # (A rotates → T2, B rotates with graced T1 → T3 killing T2, A's save of
    # T2 lands last).
    lock_path = os.path.join(d, ".rotate.lock")
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    # 0600 at creation is not enough: a pre-existing lock file keeps its
    # wider mode through the open. Force it every time (#883).
    os.fchmod(lock_fd, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        return _cmd_rotate_locked(args, d, enroll_path, box_id, token,
                                  control, sig_b64, now)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def _cmd_rotate_locked(args, d, enroll_path, box_id, token, control,
                       sig_b64, now):
    # signature: null when the box has no keypair (pre-#844 enrollment) —
    # the server may accept Bearer <redacted>-only rotation for those boxes.
    status, resp = _http(
        "POST", control.rstrip("/") + "/v1/boxes/token/rotate",
        {"signature": sig_b64},
        {"Authorization": "Bearer " + token})
    if status == 404 and _plane_missing(resp):
        # _http's synthesized 404 fallback (no JSON body at all): the
        # plane does not implement the endpoint yet — do NOT report this
        # as any other failure class.
        print("rotation failed: this control plane does not implement "
              "POST /v1/boxes/token/rotate yet (shipped on the hosted plane "
              "2026-10-02 — verify your control plane is current) — "
              "nothing was changed locally")
        return 1
    if status == 401:
        print(f"rotation rejected ({_plane_error(resp, status)}): this box "
              "token is dead (expired, revoked, or never valid) — re-pair "
              "the box (`request` + `redeem`)")
        return 1
    if status == 403:
        # Bearer <redacted> accepted but the proof was rejected: do NOT re-pair —
        # the enrollment is fine, the proof or the plane is at fault.
        print(f"rotation refused ({_plane_error(resp, status)}): the plane "
              "rejected the proof-of-possession signature — check the box "
              "clock (window is ±300 s) and the plane, then retry; the "
              "current token is untouched")
        return 1
    if status != 200 or not resp.get("ok") or not resp.get("token"):
        print(f"rotation failed: {_plane_error(resp, status)}")
        return 1
    new_exp = resp.get("token_expires_at")
    if (not isinstance(new_exp, int) or isinstance(new_exp, bool)
            or new_exp <= now or new_exp - now > MAX_TOKEN_LIFETIME):
        # Never persist a token the plane did not bound: a missing, past,
        # or absurdly long expiry defeats #846's short-lived-token goal.
        # The old enrollment.json is untouched; the plane's previous-token
        # grace keeps the old token usable for the retry.
        print("rotation failed: plane returned an unusable token expiry — "
              "nothing was saved, re-run `rotate`")
        return 1
    if sig_b64 is not None and resp.get("proof") != "ed25519":
        # Fail closed on proof-of-possession: we sent a signature, so the
        # plane skipping its verification would make the headline property
        # ("a stolen Bearer <redacted> alone cannot rotate the box out") theater.
        print(f"rotation failed: plane did not verify the proof-of-possession "
              f"signature (proof={resp.get('proof')!r}) — refusing to save; "
              "fix the plane or re-pair the box")
        return 1
    tmp = enroll_path + ".tmp"
    _write_private(tmp, json.dumps(
        {"box_id": box_id, "token": resp["token"],
         "token_expires_at": new_exp, "control": control},
        indent=2).encode())
    os.replace(tmp, enroll_path)
    exp = time.strftime("%Y-%m-%d %H:%M %Z", time.localtime(new_exp))
    print(f"rotated box token for {_plane_text(box_id)} "
          f"(proof: {_plane_text(resp.get('proof', 'unknown'))}); "
          f"new token expires {exp}")
    if resp.get("rekey_recommended"):
        print("note: the plane has no keypair for this box — re-pair "
              "(`request` + `redeem`) to get proof-of-possession rotation")
    return 0


def cmd_revoke(args):
    control, msg = _resolve_control(args)
    if control is None:
        print(msg)
        return 1
    box_id = args.box_id
    status, resp = _http(
        "POST", control.rstrip("/") + "/v1/boxes/"
        + urllib.parse.quote(box_id, safe="") + "/revoke", None,
        {"Authorization": "Bearer " + _owner_key(args)})
    if status == 404 and _plane_missing(resp):
        # _http's synthesized 404 fallback (no JSON body at all): the
        # plane does not implement the endpoint yet — not "no such box".
        print("revoke failed: this control plane does not implement "
              "POST /v1/boxes/{id}/revoke yet (shipped on the hosted plane "
              "2026-10-02 — verify your control plane is current) — "
              "nothing was revoked")
        return 1
    if status == 404:
        print(f"no such box: {box_id}")
        return 1
    if status != 200 or not resp.get("ok"):
        print(f"revoke failed: {_plane_error(resp, status)}")
        return 1
    print(f"revoked the box token for {box_id} — its heartbeats are "
          "rejected immediately")
    return 0


# ---- #864: interim box-side heartbeat sender ----------------------------------
# The control plane's heartbeat contract (POST /v1/boxes/{id}/heartbeat,
# box Bearer <redacted>, JSON status -> {ok:true}) had no in-repo producer —
# the fleet dashboard's staleness chips were only as honest as a sender
# that did not exist. This is the interim sender: one-shot, cron-acceptable
# (like `rotate --auto`), no box long-lived process. The persistent
# box-side process for #847's phone-home WebSocket lives with the S5 box
# WSS client, not here.
#
# Contract with the operator:
#   * exit 0 ONLY when the plane actually answered 200 {ok:true}. A missed
#     heartbeat never fabricates an ok — every other outcome exits 1.
#   * failures are loud: every failure prints to stderr AND is appended to
#     heartbeat.log in the state dir (cron mails stderr; the log survives
#     even when it doesn't).
#   * success is quiet: a healthy box emits nothing per tick, so the
#     every-minute cron line stays silent.
#   * the token is never printed and never written to the log; the log
#     carries only timestamps, box ids, and failure classes.
#   * concurrent invocations (slow plane vs 60 s cron cadence) serialize on
#     a lock file rather than doubling heartbeats.


def _fail(d, msg, redact=(), tag="heartbeat", log="heartbeat.log"):
    """Fail loud: stderr + appended to <log> in the state dir.

    `redact` lists secret values that must never reach either channel: any
    occurrence is replaced with <redacted> (defense in depth — the failure
    classes above never include the token themselves, but an error string
    echoed back by a misbehaving plane must not become a credential leak
    in a local log). `tag`/`log` let the box-side cron commands share the
    loud-failure shape (heartbeat, ingest) without cross-writing logs.
    """
    for secret in redact:
        if secret:
            msg = msg.replace(secret, "<redacted>")
    line = (f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {tag} FAILED: "
            f"{msg}")
    print(line, file=sys.stderr)
    try:
        with open(os.path.join(d, log), "a") as f:
            f.write(line + "\n")
    except OSError:
        pass  # stderr is the loud channel; a broken log must not mask it


def _box_uptime_s():
    try:
        with open("/proc/uptime") as f:
            return int(float(f.read().split()[0]))
    except (OSError, ValueError, IndexError):
        return None  # non-Linux box: omit rather than fail the heartbeat


def _status_body(box_id, token_expires_at):
    # Small, honest, bounded: identity + when this tick was sent + the
    # box's own view of its health. No secrets, no chat transcripts, no
    # unbounded fields — the plane is free to ignore unknown keys.
    body = {"box_id": box_id, "sent_at": int(time.time()),
            "client": USER_AGENT}
    up = _box_uptime_s()
    if up is not None:
        body["uptime_s"] = up
    try:
        body["load_1"] = round(os.getloadavg()[0], 2)
    except OSError:
        pass
    if isinstance(token_expires_at, int) and not isinstance(
            token_expires_at, bool):
        # Self-report only: the plane enforces expiry from its own store.
        body["token_expires_at"] = token_expires_at
    return body


def _heartbeat_result(d, box_id, token, sent_at, status, resp):
    if not isinstance(resp, dict):
        # _http returns json.loads() of any 2xx body — it can be a list,
        # string, or null. Anything that isn't an object cannot carry the
        # plane's {ok:true}; treat it as malformed, not as success.
        _fail(d, f"heartbeat failed: malformed plane response "
                 f"(http={status}, non-object body) — will retry at the "
                 "next cron tick", redact=(token,))
        return 1
    if status == 200 and resp.get("ok"):
        # The plane's own ok — nothing else counts as a delivered heartbeat.
        _write_private(os.path.join(d, "last_heartbeat.json"), json.dumps(
            {"box_id": box_id, "last_ok_at": sent_at,
             "plane_ok": True}, indent=2).encode())
        return 0
    if status == 401:
        _fail(d, f"heartbeat rejected ({_plane_error(resp, status)}): this "
                 "box token is dead (expired, revoked, or never valid) — "
                 "re-pair the box (`request` + `redeem`)",
              redact=(token,))
        return 1
    if status == 404 and _plane_missing(resp):
        # _http's synthesized 404 fallback (no JSON body at all): the
        # plane does not implement the endpoint yet — not "no such box".
        _fail(d, "heartbeat failed: this control plane does not implement "
                 "POST /v1/boxes/{id}/heartbeat yet — nothing was changed",
              redact=(token,))
        return 1
    _fail(d, f"heartbeat failed: {_plane_error(resp, status)} "
             f"(http={status}) — will retry at the next cron tick",
          redact=(token,))
    return 1


def cmd_heartbeat(args):
    d = _state_dir(args)
    enroll_path = os.path.join(d, "enrollment.json")
    try:
        enroll = _read_json_file(enroll_path)
    except (OSError, ValueError) as e:
        # The cron path must never die with a traceback on a corrupted
        # state file.
        _fail(d, f"enrollment.json is unreadable ({e}) — "
                 "run `request` + `redeem` first")
        return 1
    if not isinstance(enroll, dict):
        # Valid JSON but not an object (a list, string, null): .get() below
        # would AttributeError with no log entry — same loud failure instead.
        _fail(d, "enrollment.json is not an object — "
                 "run `request` + `redeem` first")
        return 1
    box_id, token = enroll.get("box_id"), enroll.get("token")
    if not box_id or not token:
        _fail(d, "enrollment.json is missing box_id/token — "
                 "run `request` + `redeem` first")
        return 1
    control, msg = _resolve_control(args, enroll)
    if control is None:
        _fail(d, msg)
        return 1
    url = (control.rstrip("/") + "/v1/boxes/"
           + urllib.parse.quote(box_id, safe="") + "/heartbeat")
    body = _status_body(box_id, enroll.get("token_expires_at"))
    # Serialize the network call under a lock: a slow plane plus a 60 s
    # cron cadence can otherwise overlap two invocations, and an
    # overlapped retry doubles the load on an already-struggling plane.
    # Reads enrollment.json only — rotate's atomic temp+rename save means
    # we can never read a half-written token.
    lock_path = os.path.join(d, ".heartbeat.lock")
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        # 0600 at creation is not enough: a pre-existing lock file keeps
        # its wider mode through the open. Force it every time (#883).
        os.fchmod(lock_fd, 0o600)
    except OSError as e:
        _fail(d, f"heartbeat FAILED: cannot open lock file ({e}) — "
                 "check state-dir permissions")
        return 1
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        status, resp = _http(
            "POST", url, body, {"Authorization": "Bearer " + token})
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)
    return _heartbeat_result(d, box_id, token, body["sent_at"], status, resp)


# Plane-supplied pairing fields are printed for the owner's visual
# verification; control characters (CR, ANSI escapes, DEL, C1 controls)
# would let a hostile plane make the terminal RENDER the expected
# fingerprint while the underlying string differs, defeating the
# comparison (B2). Rows carrying them are malformed. C1 (U+0080-U+009F)
# is included: the HTTP layer decodes JSON to str, so these are
# unambiguous control characters here — unlike the byte-level bash case,
# stripping them cannot corrupt legitimate multibyte text (#915 review).
_PAIRING_FIELD_CONTROL = re.compile(r"[\x00-\x1f\x7f\x80-\x9f]")


def _plane_text(v):
    """Strip terminal control characters from a plane-supplied value
    (#902). Display-only scrub: a hostile plane could embed ANSI escapes
    / carriage returns / C1 controls in any string it returns, and
    several commands print those values to the operator's terminal.
    Non-strings pass through unchanged; total, never raises. Stored
    values and control-flow comparisons always use the raw value — this
    is for terminal display only."""
    if isinstance(v, str):
        return _PAIRING_FIELD_CONTROL.sub("", v)
    return v


def _plane_error(resp, status):
    """Scrub a plane-supplied error string for terminal display (#902).

    Plane `error` strings are echoed into stdout (and, via `_fail`, into
    heartbeat.log) by every command's failure path — a hostile plane
    could embed ANSI escapes / carriage returns in them (terminal
    injection, cosmetic-spoofing class). No trust decision hinges on
    these strings (unlike the fingerprint ceremony's `_pairing_row`
    fields, which reject control characters outright), so
    sanitize-and-show is the right treatment: strip the control
    characters and print the cleaned text rather than refusing the
    whole message. Total: never raises; non-string values (e.g. the
    numeric `status` fallback) pass through unchanged.
    """
    return _plane_text(resp.get("error", status))


def _pairing_row(p):
    """Extract (id, box_name, fingerprint) from a plane pairing row, or
    None when the row is malformed (#881, B2). The approve/list path is
    interactive, so the bar is "never traceback on plane shape": a
    malformed or hostile plane's rows get a clean error, not silence and
    not a KeyError traceback. Fields must be non-empty strings without
    control characters — the fingerprint ceremony is this command's
    security check, and terminal-escape injection must not reach it."""
    if not isinstance(p, dict):
        return None
    pid, name, fp = p.get("id"), p.get("box_name"), p.get("fingerprint")
    if not all(isinstance(v, str) and v
               and not _PAIRING_FIELD_CONTROL.search(v)
               for v in (pid, name, fp)):
        return None
    return pid, name, fp


def cmd_approve(args):
    control, msg = _resolve_control(args)
    if control is None:
        print(msg)
        return 1
    base = control.rstrip("/") + "/v1/pairing"
    if args.bootstrap:
        # One-shot fresh-database bootstrap: no owner key exists yet, so the
        # server accepts the typed pairing code with no Authorization
        # header (see pairing/README.md). Requires --pairing-id: there is
        # no owner key to list with.
        if not args.pairing_id:
            print("--bootstrap requires --pairing-id (no owner key to list with)")
            return 1
        auth = {}
    else:
        auth = {"Authorization": "Bearer " + _owner_key(args)}

    if args.pairing_id:
        pid = args.pairing_id
    else:
        status, resp = _http("GET", base, headers=auth)
        if status != 200 or not resp.get("ok"):
            print(f"list failed: {_plane_error(resp, status)}")
            return 1
        pairs = resp.get("pairings", [])
        if not isinstance(pairs, list):
            # A malformed or hostile plane: loud, not a traceback.
            print("list failed: malformed plane response "
                  "(pairings is not a list)")
            return 1
        if not pairs:
            print("no pending pairings")
            return 0
        print("Pending pairings:")
        for p in pairs:
            # The server never returns pairing codes (stored hashed);
            # match by the id the box printed at request time.
            row = _pairing_row(p)
            if row is None:
                print("list failed: malformed plane response "
                      "(pairing entry id/box_name/fingerprint is malformed)")
                return 1
            pid, name, fp = row
            print(f"  {pid}  {name}  {fp}")
        print()
        pid = input("Pairing id to approve: ").strip()
    if not pid:
        print("no pairing selected")
        return 1

    status, resp = _http("GET", f"{base}/{pid}", headers=auth)
    if status != 200 or not resp.get("ok"):
        print(f"fetch failed: {_plane_error(resp, status)}")
        return 1
    p = resp.get("pairing")
    if not isinstance(p, dict):
        # resp["pairing"] used to KeyError here on a malformed plane.
        print("fetch failed: malformed plane response "
              "(pairing is not an object)")
        return 1
    if p.get("status") != "pending":
        print(f"pairing is {_plane_text(p.get('status')) or 'unknown'} — nothing to approve")
        return 1
    row = _pairing_row(p)
    if row is None:
        # One row-shape rule for both paths: a missing/non-string/empty
        # field or a control character (terminal-escape injection into
        # the fingerprint ceremony, B2) means the owner cannot verify
        # this pairing, so the approval cannot proceed.
        print("fetch failed: malformed plane response "
              "(pairing entry id/box_name/fingerprint is malformed)")
        return 1
    _, box_name, fp = row
    print()
    print(f"  Box name:    {box_name}")
    print(f"  Fingerprint: {fp}")
    print()
    print("Compare the fingerprint above with what the BOX displays.")
    print("They must match exactly — otherwise someone is enrolling")
    print("a different key under this box's name.")
    code = input("Type the pairing code shown on the box to approve: ").strip()
    if not code:
        print("approval aborted")
        return 1
    # The server normalizes (case/spacing/dashes) and compares against the
    # stored code hash; a mismatch is a 403 and nothing is approved.
    status, resp = _http("POST", f"{base}/{pid}/approve", {"code": code},
                         headers=auth)
    if status != 200 or not resp.get("ok"):
        print(f"approve failed: {_plane_error(resp, status)}")
        return 1
    print(f"approved {pid} — the box can now redeem its token")
    return 0


# ---------------------------------------------------------------------------
# Box-side durable-command ingest (issue #874 / G49.3).
#
# The plane enqueues owner decisions as `approval_decision` commands on the
# durable channel (#848, #873). This consumer pulls them down over the
# channel-authenticated fetch (box Bearer <redacted> #846 over TLS) and stamps
# them into confirmd's answered/consumed store, so the parked agent sees the
# same Decision legs (docs/APPROVAL_CLIENT_SIGNAL.md) as for a local tap.
#
# Trust model — a decision is honored only when ALL of these hold:
#   1. It arrived over the mutually-authenticated fetch (the box Bearer <redacted>
#      is box-scoped: the plane can only deliver this box's commands).
#   2. Its payload validates (aid shape, decision word, decision_seq,
#      idempotency_key bound to box_id+aid+seq — a forged or replayed key
#      never matches).
#   3. The aid binds to a local pending/<aid>.json the box itself filed
#      (the proxy's _file_approval). A decision for an unknown aid is
#      rejected, never stamped — this is the tenant/aid binding: a box
#      only ever files its own tenant's approvals (tenant_id is null
#      pre-H10; a non-null tenant_id fails closed, this client predates
#      multi-tenant confirmd).
# Every stamped record carries `decision_origin: "plane"` plus the plane's
# (seq, idempotency_key) as the receipt — a box-local process can write
# JSON, but it cannot produce a record that traces to a plane delivery,
# and the ingest is the only writer of plane-origin records.
#
# Crash/redelivery safety mirrors the channel contract (#848):
#   - the cursor is the highest *acked* seq, never highest-fetched;
#   - stamping is idempotent (idempotency_key log + consumed/-exists check);
#   - grant minting on approve reuses confirmd's single writer
#     (proxy/grant-writer, Finding 60) with the same argv shape and
#     validations; the writer dedupes on approval_id, so a crash between
#     mint and stamp cannot double-mint on redelivery;
#   - the consumed/ write is write-if-absent (O_EXCL, like the proxy's
#     _stamp_expired_consumed): first terminal wins if confirmd's own
#     answer path races the ingest.
# ---------------------------------------------------------------------------

_INGEST_FETCH_LIMIT = 200  # mirrors the plane's per-fetch clamp (#848)
_INGEST_CURSOR_FILE = "commands_cursor.json"
_INGESTED_DECISIONS_FILE = "ingested_decisions.json"
_INGEST_LOCK_FILE = ".ingest.lock"
_INGEST_LOG_FILE = "ingest.log"
# Mirrors the proxy's _AID_RE (proxy/swap_addon.py): an aid that fails this
# must never touch the approvals store.
_INGEST_AID_RE = re.compile(r"\A[A-Za-z0-9_-]{1,64}\Z")
# Mirrors the proxy's APPROVALS_DIR default (SWAP_APPROVALS_DIR env).
_APPROVALS_DIR_DEFAULT = "/home/swapd/approvals"
# Mirrors confirmd's GRANT_WRITER default.
_GRANT_WRITER_DEFAULT = "/home/swapd/grant-writer"
# The box executor decides which plane-produced kinds it honors (#848):
# unknown kinds are acked-and-logged so one unknown kind cannot wedge the
# queue. (The dead-letter hook for poison commands is still future work —
# a command the ingest cannot execute is NOT acked and the run stops at
# it, so the next cron tick retries; see _ingest_commands.)
_HONORED_COMMAND_KINDS = ("approval_decision",)
# Bound on the idempotency log: decisions are write-once, and consumed/'s
# own prune horizon bounds how long a redelivery can matter.
_INGESTED_DECISIONS_CAP = 5000
# Mirrors confirmd's _GRANT_MINT_TIMEOUT / _GRANT_MINT_WINDOW /
# GRANT_TTL_DEFAULT (confirm/confirmd.py). The wire v1 carries no owner TTL
# choice, so the default applies to plane-approved grants (follow-up: carry
# the decided TTL on the wire).
_INGEST_GRANT_MINT_TIMEOUT = 15
_INGEST_GRANT_MINT_WINDOW = 30
_INGEST_GRANT_TTL_DEFAULT = 1


def _ingest_fail(d, msg, redact=()):
    _fail(d, msg, redact=redact, tag="ingest", log=_INGEST_LOG_FILE)


def _ingest_say(msg):
    # Audible on stdout (cron mails it / journal captures it); never
    # carries secrets — callers pass only ids, seqs, and decision words.
    print(f"ingest: {msg}", flush=True)


def _approvals_dir():
    return os.environ.get("SVM_APPROVALS_DIR", _APPROVALS_DIR_DEFAULT)


def _grant_writer():
    return os.environ.get("GRANT_WRITER", _GRANT_WRITER_DEFAULT)


def _utcnow_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _parse_expiry_ingest(exp):
    # Mirrors confirmd's _parse_expiry (Finding 53b): datetimes, not ISO
    # strings; unparseable -> None (the writer's --approval-expires check
    # is the fail-closed backstop, mirroring the local answer path).
    from datetime import datetime, timezone
    if not exp:
        return None
    try:
        dt = datetime.fromisoformat(exp)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _ingest_item_expired(item):
    from datetime import datetime, timezone
    exp = _parse_expiry_ingest(item.get("expires"))
    return exp is not None and datetime.now(timezone.utc) >= exp


def _ingest_grant_window_ok(item):
    # Mirrors confirmd's _grant_window_ok (issue #534): refuse to START the
    # mint when the remaining validity is under the worst-case mint window.
    from datetime import datetime, timezone
    exp = _parse_expiry_ingest(item.get("expires"))
    if exp is None:
        return True
    remaining = (exp - datetime.now(timezone.utc)).total_seconds()
    return remaining >= _INGEST_GRANT_MINT_WINDOW


def _ingest_file_owner(path):
    # Finding 50: the requester is the file's owner, never an argument.
    try:
        import pwd
        return pwd.getpwuid(os.stat(path).st_uid).pw_name
    except (OSError, KeyError, ImportError):
        return None


def _load_ingest_cursor(d):
    """(cursor, epoch) from commands_cursor.json.

    Returns (None, None) when the file is missing, corrupt, or
    wrong-shaped — the caller heals from the plane's acked_watermark and
    logs loudly. A missing cursor is a normal first-run state, not an
    error; a corrupt one is journaled as corruption, not silently reset.
    """
    path = os.path.join(d, _INGEST_CURSOR_FILE)
    try:
        with open(path) as f:
            cur = json.load(f)
    except FileNotFoundError:
        return None, None, "first run (no cursor file yet)"
    except (OSError, ValueError) as e:
        return None, None, f"cursor file unreadable ({e})"
    if not isinstance(cur, dict):
        return None, None, "cursor file is not an object"
    cursor, epoch = cur.get("cursor"), cur.get("epoch")
    if not isinstance(cursor, int) or isinstance(cursor, bool):
        return None, None, "cursor file has a non-integer cursor"
    if epoch is not None and (not isinstance(epoch, int)
                              or isinstance(epoch, bool)):
        return None, None, "cursor file has a non-integer epoch"
    return cursor, epoch, None


def _save_ingest_cursor(d, cursor, epoch):
    _write_private(os.path.join(d, _INGEST_CURSOR_FILE),
                   json.dumps({"cursor": cursor, "epoch": epoch},
                              indent=2).encode())


def _load_ingested(d):
    path = os.path.join(d, _INGESTED_DECISIONS_FILE)
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_ingested(d, data):
    # Bound the log: keep the newest entries by ingested_at. Decisions are
    # write-once; an entry is only needed while its command could still be
    # redelivered (lease windows are minutes; the cap is deep headroom).
    items = sorted(data.items(),
                   key=lambda kv: (kv[1].get("ingested_at", "")
                                   if isinstance(kv[1], dict) else ""))
    data = dict(items[-_INGESTED_DECISIONS_CAP:])
    _write_private(os.path.join(d, _INGESTED_DECISIONS_FILE),
                   json.dumps(data, indent=2).encode())


def _ingest_command_shape(cmd):
    """(seq, kind, payload, epoch) or None when the command row is malformed.

    A malformed row is the plane's bug: it is acked-and-logged, never
    executed and never allowed to wedge the queue.
    """
    if not isinstance(cmd, dict):
        return None
    seq, kind, payload = cmd.get("seq"), cmd.get("kind"), cmd.get("payload")
    if not isinstance(seq, int) or isinstance(seq, bool) or seq < 0:
        return None
    if not isinstance(kind, str) or not kind:
        return None
    if not isinstance(payload, dict):
        return None
    epoch = cmd.get("epoch")
    if epoch is not None and (not isinstance(epoch, int)
                              or isinstance(epoch, bool)):
        return None
    return seq, kind, payload, epoch


def _ingest_decision_payload(box_id, payload):
    """(aid, decision, decision_seq, idempotency_key) or None.

    The idempotency key must be byte-exactly the plane's canonical form
    `approval_decision:<box_id>:<aid>:<decision_seq>` (#873): a forged or
    replayed key never matches, so a tampered payload cannot pass.
    """
    aid = payload.get("aid")
    decision = payload.get("decision")
    dseq = payload.get("decision_seq")
    key = payload.get("idempotency_key")
    if not isinstance(aid, str) or not _INGEST_AID_RE.match(aid):
        return None
    if decision not in ("approve", "deny", "expire"):
        return None
    if not isinstance(dseq, int) or isinstance(dseq, bool) or dseq < 1:
        return None
    want_key = f"approval_decision:{box_id}:{aid}:{dseq}"
    if not isinstance(key, str) or key != want_key:
        return None
    return aid, decision, dseq, key


def _ingest_ack(control, box_id, token, seq):
    """Ack one executed command. Returns True only when the plane accepted
    the ack (2xx without an explicit ok:false — the ack endpoint's response
    shape is not pinned in docs/DURABLE_COMMANDS.md; the idempotent ack
    means a strict misread only costs a redelivery, never a loss)."""
    url = (control.rstrip("/") + "/v1/boxes/"
           + urllib.parse.quote(box_id, safe="") + "/commands/ack")
    try:
        status, resp = _http("POST", url, {"seqs": [seq]},
                             {"Authorization": "Bearer " + token})
    except Exception as e:  # _http is total, but stay total anyway
        return False
    if not (200 <= status < 300):
        return False
    return not (isinstance(resp, dict) and resp.get("ok") is False)


def _mint_grant(argv):
    """Subprocess seam for the single-writer grant mint (Finding 60) —
    monkeypatched in tests."""
    import subprocess
    return subprocess.run(argv, capture_output=True, text=True,
                          timeout=_INGEST_GRANT_MINT_TIMEOUT)


def _ingest_stamp_consumed(approvals, aid, record):
    """Write-if-absent consumed/<aid>.json (O_EXCL, like the proxy's
    _stamp_expired_consumed). Returns True when this call created the
    record, False when one already existed (first terminal wins)."""
    path = os.path.join(approvals, "consumed", aid + ".json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        return False
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(record, f, indent=2)
    except BaseException:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise
    return True


def _ingest_answer_record(item, aid, decision, requester, seq, key):
    """Build the answered/consumed record mirroring _answer_locked's stamp
    shape (docs/APPROVAL_CLIENT_SIGNAL.md v1 contract) plus the
    plane-origin receipt fields (additive — readers ignore unknown fields).

    `answered_by` is null: the wire v1 does not carry the plane's owner
    principal (follow-up: pin `decided_by` on the wire). `decision_origin`
    is the honest provenance marker.
    """
    rec = dict(item)
    rec.pop("_csrf", None)
    rec.pop("_csrf_nonces", None)
    rec["id"] = aid
    rec["decision"] = decision
    rec["answered_at"] = _utcnow_iso()
    rec["answered_by"] = None
    rec["requester"] = requester
    rec["decision_origin"] = "plane"
    rec["plane_seq"] = seq
    rec["idempotency_key"] = key
    return rec


def _ingest_expired_record(item, aid, requester, seq, key):
    """Build the terminal expiry record mirroring _stamp_expired_consumed's
    shape. `expired_by: "plane"` names the third stamper alongside
    confirmd/proxy (additive stamper value; readers key on
    decision == "expired", never on the stamper's identity)."""
    rec = dict(item)
    rec.pop("_csrf", None)
    rec.pop("_csrf_nonces", None)
    rec.pop("answered_at", None)
    rec.pop("answered_by", None)
    rec["id"] = aid
    rec["decision"] = "expired"
    rec["expired_at"] = _utcnow_iso()
    rec["expired_by"] = "plane"
    rec["requester"] = requester
    rec["tenant_id"] = None
    rec["decision_origin"] = "plane"
    rec["plane_seq"] = seq
    rec["idempotency_key"] = key
    return rec


def _ingest_finish_move(d, approvals, aid, rec):
    """Move an answered/ record to consumed/ and clean up.

    The consumed/ write is write-if-absent (first-terminal-wins against
    confirmd's own answer path); the answered/ cleanup is best-effort
    (confirmd's sweep collects strays, #233). Returns True when the
    terminal state is settled, False when the write failed and the run
    must retry (nothing is acked — the resume path below re-attempts the
    move instead of treating the aid as unknown)."""
    try:
        if not _ingest_stamp_consumed(approvals, aid, rec):
            _ingest_say(f"aid={aid}: lost the terminal race "
                        "(consumed/ record already exists) — "
                        "first-terminal-wins")
    except OSError as e:
        _ingest_fail(d, f"aid={aid}: consumed/ write failed ({e}) — "
                        "decision NOT settled, will retry")
        return False
    try:
        os.remove(os.path.join(approvals, "answered", aid + ".json"))
    except OSError:
        pass  # confirmd's sweep collects strays (#233)
    return True


def _ingest_stalled_record(approvals, aid, key):
    """Return our own interrupted answered/ record, if any.

    If a previous run removed the pending item but crashed before the
    consumed/ move, the aid looks "unknown" on redelivery — but the
    answered/ file with our decision_origin + idempotency_key proves it
    is ours to finish, not a foreign aid to reject.
    """
    p = os.path.join(approvals, "answered", aid + ".json")
    try:
        with open(p) as f:
            rec = json.load(f)
    except (OSError, ValueError):
        return None
    if (isinstance(rec, dict) and rec.get("decision_origin") == "plane"
            and rec.get("idempotency_key") == key
            and rec.get("id") == aid):
        return rec
    return None


def _ingest_write_answered(approvals, aid, rec):
    """Atomic tmp+replace write of the answered/ record (the human-history
    half of the stamp; the proxy reads consumed/)."""
    answered_path = os.path.join(approvals, "answered", aid + ".json")
    os.makedirs(os.path.dirname(answered_path), exist_ok=True)
    tmp = answered_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(rec, f, indent=2)
    os.replace(tmp, answered_path)


def _ingest_approval_decision(d, approvals, box_id, seq, payload, ingested):
    """Stamp one plane decision into confirmd's store.

    Returns True when the command is consumed (ack it) and False when the
    ingest must retry later (do NOT ack — the command redelivers).
    """
    shaped = _ingest_decision_payload(box_id, payload)
    if shaped is None:
        # The plane's bug, never the box's data to invent: ack-and-log so
        # a malformed row cannot wedge the queue, and never stamp garbage.
        _ingest_fail(d, f"malformed approval_decision command seq={seq} — "
                        "acked without stamping (plane bug; nothing was "
                        "written)")
        return True
    aid, decision, dseq, key = shaped

    def _mark():
        ingested[key] = {"seq": seq, "decision": decision,
                         "ingested_at": _utcnow_iso()}

    if key in ingested:
        _ingest_say(f"seq={seq} aid={aid}: already ingested "
                    f"(idempotency key) — skipping")
        return True
    consumed_path = os.path.join(approvals, "consumed", aid + ".json")
    if os.path.exists(consumed_path):
        # First terminal wins: the local answer path (or an earlier
        # ingest) already recorded the terminal state.
        _ingest_say(f"seq={seq} aid={aid}: already terminal locally — "
                    "plane decision superseded, not stamped")
        _mark()
        return True
    pending_path = os.path.join(approvals, "pending", aid + ".json")
    try:
        with open(pending_path) as f:
            item = json.load(f)
    except FileNotFoundError:
        stalled = _ingest_stalled_record(approvals, aid, key)
        if stalled is not None:
            # Our own stamp was interrupted after the pending removal:
            # resume the consumed move instead of rejecting the aid.
            _ingest_say(f"seq={seq} aid={aid}: resuming interrupted stamp")
            if _ingest_finish_move(d, approvals, aid, stalled):
                _mark()
                return True
            return False
        # The tenant/aid binding: this box never filed this aid, so the
        # decision is not ours to stamp — reject it, never stamp it.
        _ingest_fail(d, f"seq={seq}: decision for unknown aid {aid} — no "
                        "local pending item; rejecting (not stamped)")
        _mark()
        return True
    except (OSError, ValueError) as e:
        # A torn/unreadable pending file reads as "not found" on the
        # local answer path (issue #77 L5) — same here: ack-and-log.
        _ingest_fail(d, f"seq={seq} aid={aid}: pending item unreadable "
                        f"({e}) — acked without stamping")
        _mark()
        return True
    if not isinstance(item, dict):
        _ingest_fail(d, f"seq={seq} aid={aid}: pending item is not an "
                        "object — acked without stamping")
        _mark()
        return True
    if item.get("tenant_id") is not None:
        # Pre-H10 tenant_id is always null; a scoped item means the box
        # predates multi-tenant confirmd. Fail closed: the decision stays
        # queued for an upgraded client rather than landing in the wrong
        # tenant's store.
        _ingest_fail(d, f"seq={seq} aid={aid}: tenant-scoped item "
                        "(tenant_id set) — this client predates H10; "
                        "failing closed, not acked")
        return False
    requester = item.get("requester") or _ingest_file_owner(pending_path)
    if requester not in ("bdrive", "swapd"):
        # Finding 50: only the proxy's filers may own a decidable item.
        _ingest_fail(d, f"seq={seq} aid={aid}: unexpected requester "
                        f"{requester!r} — refusing to stamp")
        _mark()
        return True

    def _remove_pending():
        try:
            os.remove(pending_path)
        except OSError:
            pass  # confirmd's reap may have won the race; not an error

    def _stamp_expired():
        rec = _ingest_expired_record(item, aid, requester, seq, key)
        if not _ingest_stamp_consumed(approvals, aid, rec):
            _ingest_say(f"seq={seq} aid={aid}: lost the terminal race "
                        "(consumed/ record already exists) — "
                        "first-terminal-wins")
        _remove_pending()
        _mark()

    if decision == "expire" or _ingest_item_expired(item):
        # A plane `expire`, or the window lapsed before the ingest ran:
        # the honest outcome label is expired either way.
        _stamp_expired()
        _ingest_say(f"seq={seq} aid={aid}: stamped expired "
                    f"(plane_seq={seq})")
        return True

    if decision == "deny":
        rec = _ingest_answer_record(item, aid, "deny", requester, seq, key)
        _ingest_write_answered(approvals, aid, rec)
        _remove_pending()
        # Finding 56: one-way. The O_EXCL move inside _ingest_finish_move
        # keeps first-terminal-wins against confirmd's own answer path.
        if not _ingest_finish_move(d, approvals, aid, rec):
            return False
        _mark()
        _ingest_say(f"seq={seq} aid={aid}: stamped denied "
                    f"(plane_seq={seq})")
        return True

    # decision == "approve": mirror _answer_locked's mint path (Findings
    # 60/64) — the grant is minted via the single writer BEFORE the
    # answered record exists.
    name = item.get("credential")
    host = item.get("host")
    method = (item.get("method") or "").upper()
    if not name or not host or not method:
        # Finding 64: the tuple is validated before the mint, never after.
        _ingest_fail(d, f"seq={seq} aid={aid}: cannot mint grant — missing "
                        "credential/host/method; failing closed, not acked")
        return False
    if not _ingest_grant_window_ok(item):
        # Issue #534: an expiry crossing mid-mint would land an
        # un-revokable grant — refuse the mint, stamp expired honestly.
        _stamp_expired()
        _ingest_say(f"seq={seq} aid={aid}: approve arrived inside the "
                    "grant-mint window — stamped expired")
        return True
    ttl_hours = _INGEST_GRANT_TTL_DEFAULT  # wire v1 carries no TTL choice
    mint_argv = [_grant_writer(), "add",
                 "--credential", name,
                 "--host", host,
                 "--method", method,
                 "--path-prefix", item.get("path_prefix") or "/",
                 "--approval-id", aid,
                 "--scope", item.get("scope") or "",
                 "--job", item.get("job") or "",
                 "--ttl-hours", str(ttl_hours)]
    if item.get("expires"):
        # Issue #294: the writer fails closed at mint time (exit 3) when
        # the instant crossed while we were working.
        mint_argv += ["--approval-expires", str(item["expires"])]
    try:
        out = _mint_grant(mint_argv)
    except Exception as e:
        _ingest_fail(d, f"seq={seq} aid={aid}: grant mint failed ({e}) — "
                        "not stamped, will retry")
        return False
    if out.returncode == 3:
        # The approval's expiry crossed during the mint: the honest
        # outcome is expired (#240 routing), not a phantom approval.
        _stamp_expired()
        _ingest_say(f"seq={seq} aid={aid}: writer refused (expiry crossed) "
                    "— stamped expired")
        return True
    if out.returncode != 0:
        _ingest_fail(d, f"seq={seq} aid={aid}: grant mint failed "
                        f"(exit {out.returncode}) — not stamped, will retry")
        return False
    rec = _ingest_answer_record(item, aid, "approve", requester, seq, key)
    rec["grant_ttl_hours"] = ttl_hours
    _ingest_write_answered(approvals, aid, rec)
    _remove_pending()
    # The grant is minted (the writer dedupes on approval_id, so a
    # redelivery re-mint is a no-op); a failed move retries the *stamp*,
    # never the mint — the resume path re-attempts the move.
    if not _ingest_finish_move(d, approvals, aid, rec):
        return False
    _mark()
    _ingest_say(f"seq={seq} aid={aid}: stamped approved and minted grant "
                f"(plane_seq={seq})")
    return True


def _ingest_commands(d, approvals, box_id, token, control):
    """One fetch-execute-ack pass over the durable command queue.

    Returns 0 when the pass completed (every due command acked or the
    queue drained), 1 when it did not (loud log already written).
    """
    cursor, epoch, cursor_note = _load_ingest_cursor(d)
    healed = cursor is None
    params = {"since": cursor or 0, "limit": _INGEST_FETCH_LIMIT}
    url = (control.rstrip("/") + "/v1/boxes/"
           + urllib.parse.quote(box_id, safe="") + "/commands/pending?"
           + urllib.parse.urlencode(params))
    status, resp = _http("GET", url, None,
                         {"Authorization": "Bearer " + token})
    if status == 401:
        _ingest_fail(d, f"ingest rejected ({_plane_error(resp, status)}): "
                        "this box token is dead (expired, revoked, or "
                        "never valid) — re-pair the box (`request` + "
                        "`redeem`)", redact=(token,))
        return 1
    if status == 404 and _plane_missing(resp):
        _ingest_fail(d, "ingest failed: this control plane does not "
                        "implement the commands endpoints yet — nothing "
                        "was changed", redact=(token,))
        return 1
    if not isinstance(resp, dict) or status != 200:
        _ingest_fail(d, f"ingest failed: {_plane_error(resp, status)} "
                        f"(http={status}) — will retry at the next cron "
                        "tick", redact=(token,))
        return 1
    commands = resp.get("commands")
    if not isinstance(commands, list):
        _ingest_fail(d, "ingest failed: malformed plane response "
                        "(commands is not a list) — will retry at the "
                        "next cron tick", redact=(token,))
        return 1
    watermark = resp.get("acked_watermark")
    if healed:
        # Reconcile from the plane's own watermark (the cursor contract,
        # #848): a missing/corrupt cursor file heals to the highest acked
        # seq, never to zero — zero would redeliver ancient history.
        cursor = watermark if isinstance(watermark, int) \
            and not isinstance(watermark, bool) else 0
        if cursor_note.startswith("first run"):
            _ingest_say(f"no cursor file yet — starting at plane "
                        f"acked_watermark={cursor}")
        else:
            # Corruption is journal-worthy on the loud channel; the run
            # still continues from the healed cursor.
            _ingest_fail(d, f"cursor healed from plane acked_watermark="
                            f"{cursor} ({cursor_note})", redact=(token,))
    ingested = _load_ingested(d)
    # Ascending seq order; the cursor advances only over the acked prefix
    # (never past an unacked command — that would skip its redelivery).
    rows = []
    for cmd in commands:
        shaped = _ingest_command_shape(cmd)
        if shaped is None:
            # No seq to ack and nothing safe to execute: skip loudly. The
            # plane will return the row on every fetch until it is fixed —
            # noisy, but the alternative (advancing past it blindly) hides
            # a plane bug, and acking without a seq is impossible.
            _ingest_fail(d, "malformed command row from plane — skipped "
                            "(plane bug; nothing was written)",
                         redact=(token,))
            continue
        rows.append(shaped)
    rows.sort(key=lambda r: r[0])
    new_cursor = cursor
    ok = True
    for seq, kind, payload, cmd_epoch in rows:
        if seq <= new_cursor:
            continue  # already acked (defense: the plane should not send it)
        if cmd_epoch is not None and cmd_epoch != epoch:
            _ingest_say(f"epoch {epoch} -> {cmd_epoch} (plane moved on)")
            epoch = cmd_epoch
        if kind not in _HONORED_COMMAND_KINDS:
            # The plane is opaque to kinds and the box executor decides;
            # ack-and-log keeps one unknown kind from wedging the queue.
            _ingest_say(f"seq={seq}: unknown command kind {kind!r} — "
                        "acked without execution")
            consumed = True
        elif kind == "approval_decision":
            try:
                consumed = _ingest_approval_decision(d, approvals, box_id,
                                                     seq, payload, ingested)
            except (OSError, ValueError) as e:
                # A local I/O failure (disk full, torn state) must fail
                # closed with a loud log — never a traceback, and never
                # an ack: the command redelivers on the next tick.
                _ingest_fail(d, f"seq={seq}: local failure during ingest "
                                f"({e}) — not acked, will retry",
                             redact=(token,))
                consumed = False
        else:  # pragma: no cover — registry and branch above stay in sync
            consumed = False
        if not consumed:
            ok = False
            break  # stop at the first un-ackable command; the rest wait
        if not _ingest_ack(control, box_id, token, seq):
            _ingest_fail(d, f"seq={seq}: ack failed — cursor held at "
                            f"{new_cursor}; will retry at the next cron "
                            "tick", redact=(token,))
            ok = False
            break
        new_cursor = seq
    _save_ingest_cursor(d, new_cursor, epoch)
    _save_ingested(d, ingested)
    if ok and new_cursor > cursor:
        _ingest_say(f"ingested {new_cursor - cursor} command(s); "
                    f"cursor -> {new_cursor}")
    elif ok:
        _ingest_say("queue drained; nothing due")
    return 0 if ok else 1


def cmd_ingest(args):
    """Box: pull durable commands and ingest plane approval decisions
    (cron-friendly: exit 0 only when every due command was consumed,
    loud on failure, quiet-ish on success)."""
    d = _state_dir(args)
    enroll_path = os.path.join(d, "enrollment.json")
    try:
        enroll = _read_json_file(enroll_path)
    except (OSError, ValueError) as e:
        _ingest_fail(d, f"enrollment.json is unreadable ({e}) — run "
                        "`request` + `redeem` first")
        return 1
    if not isinstance(enroll, dict):
        _ingest_fail(d, "enrollment.json is not an object — run `request` "
                        "+ `redeem` first")
        return 1
    box_id, token = enroll.get("box_id"), enroll.get("token")
    if not box_id or not token:
        _ingest_fail(d, "enrollment.json is missing box_id/token — run "
                        "`request` + `redeem` first")
        return 1
    control, msg = _resolve_control(args, enroll)
    if control is None:
        _ingest_fail(d, msg)
        return 1
    approvals = _approvals_dir()
    if not os.path.isdir(approvals):
        _ingest_fail(d, f"approvals dir {approvals} is missing — is "
                        "confirmd installed on this box?", redact=(token,))
        return 1
    # Serialize overlapping cron ticks: two ingests racing the same queue
    # would double-stamp (the idempotency log covers crashes, not
    # concurrency — keep it serial).
    lock_path = os.path.join(d, _INGEST_LOCK_FILE)
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        os.fchmod(lock_fd, 0o600)
    except OSError as e:
        _ingest_fail(d, f"ingest FAILED: cannot open lock file ({e}) — "
                        "check state-dir permissions", redact=(token,))
        return 1
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        return _ingest_commands(d, approvals, box_id, token, control)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="spark-pair",
                                 description="pairing-code box enrollment")
    ap.add_argument("--dir", help="state dir (default ~/.config/spark-pair)")
    ap.add_argument("--control", help="control-plane base URL")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="generate the box ed25519 keypair")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("request", help="request a pairing code")
    s.add_argument("--name", required=True, help="human box name")
    s.set_defaults(fn=cmd_request)

    s = sub.add_parser("redeem", help="wait for approval, redeem box token")
    s.set_defaults(fn=cmd_redeem)

    s = sub.add_parser("heartbeat", help="box: send one liveness heartbeat "
                                      "to the control plane (cron-friendly: "
                                      "exit 0 only on the plane's ok, loud "
                                      "on failure, quiet on success)")
    s.set_defaults(fn=cmd_heartbeat)

    s = sub.add_parser("ingest", help="box: pull durable commands and "
                                      "ingest plane approval decisions into "
                                      "confirmd (cron-friendly: exit 0 only "
                                      "when every due command was consumed, "
                                      "loud on failure)")
    s.set_defaults(fn=cmd_ingest)

    s = sub.add_parser("approve", help="owner: verify fingerprint + approve")
    s.add_argument("--pairing-id", help="pairing id (lists pending if omitted)")
    s.add_argument("--owner-key", help="owner API key (else SVM_OWNER_KEY)")
    s.add_argument("--bootstrap", action="store_true",
                   help="fresh-database bootstrap: no owner key yet; the "
                        "typed pairing code alone approves (requires "
                        "--pairing-id)")
    s.set_defaults(fn=cmd_approve)

    s = sub.add_parser("rotate", help="box: rotate the Bearer <redacted> "
                                     "(proof of possession; plane update "
                                     "pending — see pairing/README.md)")
    s.add_argument("--auto", action="store_true",
                   help="cron-friendly: rotate only when the token expires "
                        "within --within seconds (quiet success otherwise)")
    s.add_argument("--within", type=int, default=AUTO_ROTATE_WITHIN,
                   help=f"auto-rotate threshold in seconds "
                        f"(default {AUTO_ROTATE_WITHIN})")
    s.set_defaults(fn=cmd_rotate)

    s = sub.add_parser("revoke", help="owner: revoke a box's Bearer <redacted> "
                                     "immediately (plane update pending — "
                                     "see pairing/README.md)")
    s.add_argument("--box-id", required=True, help="box id to revoke")
    s.add_argument("--owner-key", help="owner API key (else SVM_OWNER_KEY)")
    s.set_defaults(fn=cmd_revoke)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
