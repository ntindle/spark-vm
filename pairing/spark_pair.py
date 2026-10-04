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

  Filing upload (issue #953):
    spark-pair.py upload-filings             # scan confirm/pending/ and POST
                                             # new filings to the plane's
                                             # box-authenticated file endpoint
                                             # (cron ~1/min)

  Phone-home channel (issue #959, S5a connection core):
    spark-pair.py phone-home                 # hold the persistent outbound
                                             # WSS channel to the control
                                             # plane (daemon: reconnects per
                                             # the wire spec; the heartbeat
                                             # stays the only liveness signal)

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
import hashlib
import ipaddress
import json
import os
import random
import re
import signal
import socket
import ssl
import struct
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
    numeric `status` fallback) pass through unchanged. A non-dict
    response (a 2xx with a JSON list/string/null body) falls back to
    the numeric status — callers that branch on `isinstance(resp, dict)`
    may pass the raw response through safely.
    """
    if not isinstance(resp, dict):
        return _plane_text(status)
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
#      pre-H10; a non-null tenant_id on a live item fails closed — acked
#      and loudly logged — because this client predates multi-tenancy).
# Every stamped record carries `decision_origin: "plane"` plus the plane's
# (seq, idempotency_key) as the receipt. That marker is provenance
# bookkeeping inside the same DAC boundary every other store record
# relies on — a local writer with approvals-dir access can forge the
# marker the same way it can forge any record (the key format is
# deterministic and box_id lives in 0600 enrollment.json). The boundary
# the ingest actually enforces is above: only the ingest writes
# plane-origin records, and only for plane-delivered commands.
#
# NOTE (stated plainly): this promotes the plane from relay to
# grant-issuing authority — a compromised plane can mint arbitrary local
# grants through the approve path. That is the feature's purpose (the
# owner's tap moved to the plane dashboard), not an accident: the same
# trust the box already places in the plane for pairing, token rotation,
# and liveness now covers approvals.
#
# Crash/redelivery safety mirrors the channel contract (#848):
#   - the cursor is the highest *acked* seq, never highest-fetched;
#   - stamping is idempotent (idempotency_key log + consumed/-exists check);
#   - grant minting on approve reuses confirmd's single writer
#     (proxy/grant-writer, Finding 60) with the same argv shape and
#     validations; the writer dedupes on approval_id, so a crash between
#     mint and stamp cannot double-mint on redelivery;
#   - the consumed/ write is write-if-absent (O_EXCL, like the proxy's
#     _stamp_expired_consumed): first writer wins among O_EXCL stampers
#     (the reapers, earlier ingests). confirmd's in-flight answer path is
#     clobbering, not O_EXCL, so it wins the *record* regardless — the
#     approve path re-checks for its terminal record after the mint
#     instead of relying on this race.
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
# Mirrors confirmd's AUDIT default (confirm/confirmd.py) and its
# _sanitize_audit_field / _AUDIT_FIELD_ALLOW_RE (#683, #17 twin): the
# audit-line format is deliberately duplicated rather than imported
# across the pairing/confirmd component boundary, like _AID_RE.
_INGEST_AUDIT_DEFAULT = "/home/swapd/confirmd/audit.log"
_INGEST_AUDIT_FIELD_RE = re.compile(r"[^!-~]")


def _ingest_audit_field(value):
    if value is None:
        return "-"
    return _INGEST_AUDIT_FIELD_RE.sub("", str(value))


def _ingest_audit(d, aid, decision, requester, seq, ttl_hours=None):
    """Append one `answer` audit line for a plane-stamped decision.

    Mirrors confirmd's audit_log("answer", ...) shape plus
    decision_origin=plane — plane decisions must not bypass the audit
    trail the rest of the system treats as load-bearing (the proxy and
    grant-writer treat the audit write as part of authorization, and
    the sentinel feed ships the signed audit log). A single O_APPEND
    write: the ingest runs ~1/min, so no rotation here (confirmd's
    rotation owns the segment size). On failure the event is treated
    as lost and named loudly on stderr — confirmd's posture: the audit
    call happens after the decision, so the stamp stands and the trail
    gap is operator-visible.
    """
    from datetime import datetime, timezone
    detail = ("id=%s decision=%s requester=%s decision_origin=plane "
              "plane_seq=%s" % (aid, decision, requester, seq))
    if decision == "approve" and ttl_hours is not None:
        detail += " ttl=%dh" % ttl_hours
    line = ("ts=%s event=%s peer=%s login=%s %s\n"
            % (datetime.now(timezone.utc).isoformat(timespec="seconds"),
               _ingest_audit_field("answer"),
               _ingest_audit_field("plane"),
               _ingest_audit_field(""),  # wire v1: no owner principal
               _ingest_audit_field(detail)))
    path = os.environ.get("CONFIRM_AUDIT", _INGEST_AUDIT_DEFAULT)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o640)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
    except OSError as e:
        _ingest_fail(d, f"aid={aid}: LOST AUDIT EVENT event=answer "
                        f"decision={decision} ({e}) — the stamp stands; "
                        "the trail gap is operator-visible")
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
# choice, so the default applies to plane-approved grants (wire v2 carries
# the decided TTL: #946).
_INGEST_GRANT_MINT_TIMEOUT = 15
_INGEST_GRANT_MINT_WINDOW = 30
_INGEST_GRANT_TTL_DEFAULT = 1


def _ingest_fail(d, msg, redact=()):
    _fail(d, msg, redact=redact, tag="ingest", log=_INGEST_LOG_FILE)


def _ingest_say(msg, redact=()):
    # Audible on stdout (cron mails it / journal captures it). `redact`
    # lists secret values that must never reach the channel — used where
    # plane-controlled strings are echoed (defense in depth: the failure
    # classes never include the token themselves, but a hostile plane
    # could echo it back inside a field we print).
    for secret in redact:
        if secret:
            msg = msg.replace(secret, "<redacted>")
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

    A malformed row is the plane's bug: it is skipped loudly WITHOUT
    acking — the cursor holds, the run stops at the bad row, and the
    plane repairs it. Never executed, never allowed to wedge the queue
    silently.
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
    shape is not pinned in docs/DURABLE_COMMANDS.md).

    The 2xx acceptance is deliberately loose, and it is safe *only*
    because of execute-before-ack ordering: a loose misread (treating a
    failed ack as accepted) advances the cursor past an unacked seq, but
    the command was already executed AND the ack is idempotent — the
    plane's acked_watermark is the recovery source, and a redelivered
    command re-runs through the idempotency backstops. A *strict* misread
    (treating an accepted ack as failed) only costs a redelivery, never
    a loss. So the asymmetry favors looseness here: the dangerous
    direction is strictness-looking-safe, not looseness.
    """
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
    record, False when one already existed (first writer wins among
    O_EXCL stampers — the reapers and earlier ingests; confirmd's
    in-flight answer path is clobbering, not O_EXCL, so it wins the
    record regardless)."""
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
    if decision == "deny":
        # Issue #73 (belt-and-braces, mirroring _answer_locked): a
        # requester-planted grant_ttl_hours must not survive into the
        # answered record of a denial — deny mints nothing, so the
        # record must not claim a lifetime.
        rec.pop("grant_ttl_hours", None)
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

    The consumed/ write is write-if-absent (first writer wins among
    O_EXCL stampers — the reapers and earlier ingests; against confirmd's
    in-flight answer path the local record wins the record, so this is a
    stamper race, not a cross-process guarantee); the answered/ cleanup
    is best-effort
    (confirmd's sweep collects strays, #233). Returns True when the
    terminal state is settled, False when the write failed and the run
    must retry (nothing is acked — the resume path below re-attempts the
    move instead of treating the aid as unknown)."""
    try:
        if not _ingest_stamp_consumed(approvals, aid, rec):
            _ingest_say(f"aid={aid}: lost the terminal race "
                        "(consumed/ record already exists) — "
                        "not stamping over the winner")
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


def _ingest_approval_decision(d, approvals, box_id, token, seq, payload,
                              ingested, attention):
    """Stamp one plane decision into confirmd's store.

    Returns True when the command is consumed (ack it) and False when the
    ingest must retry later (do NOT ack — the command redelivers).
    `attention` collects operator-attention notes for permanently
    unprocessable commands (acked-and-logged, queue advances, exit 1).
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
    if item.get("tenant_id") is not None and not _ingest_item_expired(item):
        # Permanent, not transient: this client predates multi-tenant
        # confirmd (H10) and can never stamp a scoped item. Ack-and-log
        # loudly with the upgrade runbook instead of wedging the queue
        # behind it — but flag operator attention (the run exits 1)
        # because a decision was dropped on the floor. A scoped item
        # whose window already lapsed falls through to the honest
        # expired stamp below, which drains it.
        attention.append(
            f"tenant-scoped approval {aid} (seq={seq}): decision "
            f"{decision} acked without stamping — upgrade to an "
            "H10-aware ingest client")
        _ingest_fail(d, f"seq={seq} aid={aid}: tenant-scoped item "
                        "(tenant_id set) — this client predates H10; "
                        "acked without stamping (upgrade the client)",
                     redact=(token,))
        _mark()
        return True
    # Finding 50: the requester is the file's owner, never an argument —
    # only bdrive/swapd may file. The item's "requester" field (when
    # present) is requester-authored and is never consulted.
    requester = _ingest_file_owner(pending_path)
    if requester not in ("bdrive", "swapd"):
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
        if _ingest_stamp_consumed(approvals, aid, rec):
            _ingest_audit(d, aid, "expired", requester, seq)
        else:
            # The O_EXCL write lost: a reaper (or an earlier ingest)
            # recorded first, and write-if-absent means first-writer-wins
            # the record among O_EXCL stampers. (Against confirmd's
            # in-flight answer path the local record wins regardless —
            # its move is clobbering, not O_EXCL — so the "first" here
            # names the stamper race only.)
            _ingest_say(f"seq={seq} aid={aid}: lost the terminal race "
                        "(consumed/ record already exists) — "
                        "not stamping over it")
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
        # keeps first-writer-wins among O_EXCL stampers (reapers, earlier
        # ingests); against confirmd's in-flight answer the local record
        # wins regardless — see the approve-path race handling above.
        if not _ingest_finish_move(d, approvals, aid, rec):
            return False
        _ingest_audit(d, aid, "deny", requester, seq)
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
    # Shrink the approve/terminal race window: re-check the terminal
    # record immediately before the mint (the earlier check at the top of
    # this function is stale by now). The window cannot be closed — the
    # mint itself takes up to _INGEST_GRANT_MINT_TIMEOUT seconds — so the
    # post-mint re-check below is the real backstop.
    if os.path.exists(os.path.join(approvals, "consumed", aid + ".json")):
        _ingest_say(f"seq={seq} aid={aid}: terminal record appeared "
                    "before the mint — not minting (confirmd won the race)")
        _mark()
        return True
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
    # #240-style post-mint terminal re-check (mirrors _answer_locked): the
    # owner's tap — or a reaper — may have landed during the mint, and the
    # pending file still existed for all of it (the ingest holds no
    # per-aid lock against confirmd's answer path — the structural fix
    # is #945). Cross-process truth:
    # against confirmd's in-flight answer the local path wins the *record*
    # (its answered→consumed move is clobbering os.replace, not O_EXCL),
    # so "first-terminal-wins" describes the write-if-absent race against
    # the reapers only — never a guarantee against _answer_locked.
    if os.path.exists(os.path.join(approvals, "consumed", aid + ".json")):
        # The grant is minted and cannot be un-minted (no per-approval-id
        # revoke — grant-writer revoke is by job only). Journal the
        # conflict loudly with the remediation runbook instead of
        # stamping over the winner: a live grant under a deny/expired
        # record is a fail-open the proxy would honor.
        job = item.get("job") or "<job>"
        try:
            with open(os.path.join(approvals, "consumed",
                                   aid + ".json")) as f:
                winner = json.load(f)
        except (OSError, ValueError):
            winner = {}
        _ingest_fail(d, f"seq={seq} aid={aid}: APPROVE/TERMINAL RACE — "
                        "grant minted, but a terminal record landed "
                        "during the mint; NOT stamping. approval_id="
                        f"{aid} credential={item.get('credential')} "
                        f"host={item.get('host')} "
                        f"method={(item.get('method') or '').upper()} "
                        f"path_prefix={item.get('path_prefix') or '/'} "
                        f"job={job} winning_decision="
                        f"{winner.get('decision')!r}. Runbook: the "
                        "winning terminal state is in "
                        f"consumed/{aid}.json; the minted grant stays "
                        "live until its TTL expires — revoke it with "
                        f"`grant-writer revoke --job {job}` if the "
                        "winner is deny/expired.", redact=(token,))
        _mark()
        return True
    if _ingest_item_expired(item):
        # The window lapsed during the mint with no terminal record: the
        # honest outcome is expired (the #240 outcome), not a phantom
        # approval for an already-dead window.
        _stamp_expired()
        _ingest_say(f"seq={seq} aid={aid}: window lapsed during the mint "
                    "— stamped expired")
        _mark()
        return True
    rec = _ingest_answer_record(item, aid, "approve", requester, seq, key)
    rec["grant_ttl_hours"] = ttl_hours
    _ingest_write_answered(approvals, aid, rec)
    _remove_pending()
    # The grant is minted (the writer dedupes on approval_id, so a
    # redelivery re-mint is a no-op); a failed move retries the *stamp*,
    # never the mint — the resume path re-attempts the move.
    if not _ingest_finish_move(d, approvals, aid, rec):
        return False
    _ingest_audit(d, aid, "approve", requester, seq, ttl_hours=ttl_hours)
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
    if epoch is not None:
        # #947: incarnation claim — the box asserts the epoch it knows on
        # every fetch so the plane can detect a stale-epoch box and force
        # re-sync (detection itself is #848/#958 scope; the box only ever
        # asserts what it knows). Omitted when the cursor has no epoch
        # (first run) so a fresh box never claims a bogus epoch=0.
        params["epoch"] = epoch
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
    attention = []
    for seq, kind, payload, cmd_epoch in rows:
        if seq <= new_cursor:
            continue  # already acked (defense: the plane should not send it)
        if cmd_epoch is not None and cmd_epoch != epoch:
            # Epoch adoption is last-writer-wins: the plane is the
            # authority on which delivery-generation this pass belongs to,
            # and the epoch is carried back in the ack envelope for
            # diagnostics only. Two planes racing the same box would
            # interleave epochs the box cannot arbitrate — the box-side
            # cursor stays monotonic regardless. The box asserts its epoch
            # claim on every fetch (?epoch=, #947) so the plane can detect
            # a stale-epoch box and force re-sync. Adoption is
            # last-writer-wins (monotonic in the single-plane case); the
            # box never writes plane state, so it cannot regress the
            # plane's epoch.
            _ingest_say(f"epoch {epoch} -> {cmd_epoch} (plane moved on)")
            epoch = cmd_epoch
        if kind not in _HONORED_COMMAND_KINDS:
            # The plane is opaque to kinds and the box executor decides;
            # ack-and-log keeps one unknown kind from wedging the queue.
            # `kind` is plane-controlled: redact like any plane string
            # that reaches a cron-spooled channel.
            _ingest_say(f"seq={seq}: unknown command kind {kind!r} — "
                        "acked without execution", redact=(token,))
            consumed = True
        elif kind == "approval_decision":
            try:
                consumed = _ingest_approval_decision(d, approvals, box_id,
                                                     token, seq, payload,
                                                     ingested, attention)
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
    try:
        _save_ingest_cursor(d, new_cursor, epoch)
        _save_ingested(d, ingested)
    except OSError as e:
        # ENOSPC/EACCES/EROFS on the state saves: fail closed and loud —
        # never a traceback. Redelivery stays safe: acked commands are
        # covered by the consumed/ records and the idempotency log the
        # last successful save wrote.
        _ingest_fail(d, f"state save failed ({e}) — cursor/log may be "
                        "stale; redelivery is idempotent, will retry",
                     redact=(token,))
        return 1
    if attention:
        for note in attention:
            _ingest_say("ATTENTION: " + note, redact=(token,))
    if ok and new_cursor > cursor:
        _ingest_say(f"ingested {new_cursor - cursor} command(s); "
                    f"cursor -> {new_cursor}")
    elif ok:
        _ingest_say("queue drained; nothing due")
    # Permanently-unprocessable commands were acked-and-logged above: the
    # queue advanced, but the operator still needs to see the exit code.
    return 0 if ok and not attention else 1


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


# ---------------------------------------------------------------------------
# Box-side filing uploader (issue #953 — #876 S3)
# ---------------------------------------------------------------------------
# The proxy files refused-grant approvals locally only
# (confirm/pending/<aid>.json); the plane record (#872) and the
# box-authenticated file endpoint (S2, #952) give it a destination, but
# nothing moves the filing across. upload-filings is the periodic mover:
# one scan-and-POST pass per cron tick, riding the heartbeat/ingest
# * * * * * pattern (own lock file, own log) — not folded into ingest
# (G76.2).
_UPLOAD_FILINGS_LOCK_FILE = ".upload-filings.lock"
_UPLOAD_FILINGS_LOG_FILE = "upload-filings.log"
_UPLOAD_SUMMARY_LIMIT = 250     # plane caps summary at 256 chars (#952)
_UPLOAD_DETAIL_MAX_BYTES = 4096  # plane's MAX_DETAIL_BYTES (#952)
_UPLOAD_TTL_SECS = 3600         # plane's max TTL; matches the local 1 h
# The proxy's filing summary ends with the refusal reason
# (proxy/swap_addon.py _file_approval: "%s %s%s for %s (refused: %s)").
# The reason is not stored as its own field, so the uploader reads it
# back from the pinned suffix — a repo-internal format contract, not a
# plane contract. _upload_reason anchors on the LAST " (refused: " via
# rpartition (the path can carry a literal one, percent-decoded).


def _upload_fail(d, msg, redact=()):
    _fail(d, msg, redact=redact, tag="upload-filings",
          log=_UPLOAD_FILINGS_LOG_FILE)


def _upload_say(msg, redact=()):
    # Audible on stdout (cron mails it / journal captures it), same
    # redaction discipline as _ingest_say.
    for secret in redact:
        if secret:
            msg = msg.replace(secret, "<redacted>")
    print(f"upload-filings: {msg}", flush=True)


def _upload_truncate_summary(summary):
    """Clip the local (unbounded) summary to the plane's 256-char bound:
    250 chars + "…" = 251, with headroom under the cap (G76.3)."""
    s = summary if isinstance(summary, str) else ""
    s = s.strip()
    if len(s) > _UPLOAD_SUMMARY_LIMIT:
        s = s[:_UPLOAD_SUMMARY_LIMIT] + "…"
    return s


def _upload_reason(summary):
    """Pull the refusal reason out of the proxy's pinned summary suffix.

    The suffix is the LAST " (refused: …)" in the string — the path
    portion of the summary can itself carry a literal " (refused: " (the
    proxy's _normalize_path percent-decodes to fixpoint), so a leftmost
    regex match would capture garbage. rpartition anchors on the last
    occurrence.

    Returns None when the summary does not carry the suffix (a filing
    written by a different writer) — the detail tuple stays valid
    without it. Total: a non-string summary yields None, never a
    TypeError."""
    if not isinstance(summary, str):
        return None
    _head, sep, tail = summary.rpartition(" (refused: ")
    if not sep or not tail.endswith(")"):
        return None
    return tail[:-1]


def _upload_detail(rec):
    """Build the plane detail tuple per G76.3:
    {credential, host, method, path_prefix, reason, filed_at, expires} —
    Finding-49 discipline (no free text, tuple from the real request).

    path_prefix (unbounded on the local side) is truncated with "…" while
    the full host is kept, so a pathological filing can never breach the
    plane's 4 KB detail cap. The longest fitting prefix is binary-searched
    — the bound is byte-exact, not heuristic.

    Returns (detail, None) or (None, reason) when the record cannot form
    a valid tuple."""
    tup = {}
    for key in ("credential", "host", "method", "path_prefix"):
        v = rec.get(key)
        if not isinstance(v, str) or not v:
            return None, f"record has no usable {key!r} — skipped"
        tup[key] = v
    reason = _upload_reason(rec.get("summary"))
    if reason:
        tup["reason"] = reason
    for key in ("created", "expires"):
        v = rec.get(key)
        if not isinstance(v, str) or not v:
            return None, f"record has no usable {key!r} — skipped"
        tup["filed_at" if key == "created" else "expires"] = v
    blob = json.dumps(tup).encode()
    if len(blob) <= _UPLOAD_DETAIL_MAX_BYTES:
        return tup, None
    # Over cap: shrink path_prefix only (host stays full — G76.3).
    path_prefix = tup["path_prefix"]
    lo, hi = 0, len(path_prefix)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        cand = dict(tup)
        cand["path_prefix"] = path_prefix[:mid] + "…"
        if len(json.dumps(cand).encode()) <= _UPLOAD_DETAIL_MAX_BYTES:
            lo = mid
        else:
            hi = mid - 1
    tup["path_prefix"] = path_prefix[:lo] + "…"
    if len(json.dumps(tup).encode()) > _UPLOAD_DETAIL_MAX_BYTES:
        # Even the empty prefix is over cap (a pathological host): the
        # plane would 400 with no uploader recovery — skip loudly rather
        # than POST a known-400 every tick.
        return None, "detail exceeds 4 KB even with an empty path_prefix"
    return tup, None


def _upload_one(d, box_id, token, url, aid, rec):
    """POST one pending filing. Returns (state, note) where state is
    "uploaded", "deduped", "failed", or "abort" (a token-state failure
    that poisons the whole pass)."""
    if rec.get("id") != aid:
        _upload_fail(d, f"pending/{aid}.json: record id "
                        f"{rec.get('id')!r} does not match the filename — "
                        "skipped", redact=(token,))
        return "failed", "id/filename mismatch"
    summary = _upload_truncate_summary(rec.get("summary"))
    if not summary:
        _upload_fail(d, f"pending/{aid}.json: empty summary — skipped",
                     redact=(token,))
        return "failed", "empty summary"
    detail, derr = _upload_detail(rec)
    if derr is not None:
        _upload_fail(d, f"pending/{aid}.json: {derr}", redact=(token,))
        return "failed", derr
    body = {"aid": aid, "summary": summary, "detail": detail,
            "expires_in_secs": _UPLOAD_TTL_SECS}
    status, resp = _http("POST", url, body,
                         {"Authorization": "Bearer " + token})
    if status == 401:
        _upload_fail(d, f"upload rejected ({_plane_error(resp, status)}): "
                        "this box token is dead (expired, revoked, or "
                        "never valid) — re-pair the box (`request` + "
                        "`redeem`); pass aborted", redact=(token,))
        return "abort", "token dead"
    if status == 404 and _plane_missing(resp):
        _upload_fail(d, "upload failed: this control plane does not "
                        "implement POST /v1/boxes/{id}/approvals/file yet "
                        "— nothing was changed; pass aborted",
                     redact=(token,))
        return "abort", "endpoint missing"
    if not isinstance(resp, dict) or status not in (200, 201) \
            or not resp.get("ok") or resp.get("aid") != aid:
        # A plane outage degrades loudly but never touches the local
        # filing: the pending record stays, the next tick retries (G76.2).
        _upload_fail(d, f"pending/{aid}.json: upload failed: "
                        f"{_plane_error(resp, status)} (http={status}) — "
                        "will retry at the next cron tick", redact=(token,))
        return "failed", f"http={status}"
    if resp.get("deduped"):
        return "deduped", "already on the plane"
    return "uploaded", "filed"


def _upload_filings(d, approvals, box_id, token, control):
    """One scan-and-POST pass over confirm/pending/.

    Returns 0 when every pending filing was uploaded or already on the
    plane (deduped), 1 otherwise. Pending-only by construction (G76.4):
    the scan reads the pending store itself — denied, expired-stamped,
    and consumed records live elsewhere and are never seen. A record
    whose local expiry already passed is skipped too: it is on its way
    to consumed/ and uploading it would mint a plane-side ghost.
    """
    pending = os.path.join(approvals, "pending")
    # G76.7 writer identity: the pending dir must be box-service-owned
    # (bdrive/swapd) — never an agent-writable path. This directory gate
    # is only a coarse sanity check: the real Finding-50 enforcement is
    # the per-file owner check before each read below (ingest enforces
    # per record; the uploader matches it). A box-owned but
    # agent-writable dir would otherwise let an agent plant filings the
    # box then POSTs in its own name.
    owner = _ingest_file_owner(pending)
    if owner not in ("bdrive", "swapd"):
        _upload_fail(d, f"pending dir {pending} is owned by {owner!r} — "
                        "refusing to upload (writer identity must be the "
                        "box, never the agent)", redact=(token,))
        return 1
    try:
        names = sorted(os.listdir(pending))
    except OSError as e:
        _upload_fail(d, f"cannot list pending dir {pending} ({e}) — "
                        "is confirmd installed on this box?", redact=(token,))
        return 1
    url = (control.rstrip("/") + "/v1/boxes/"
           + urllib.parse.quote(box_id, safe="") + "/approvals/file")
    uploaded = deduped = skipped = failed = 0
    for fn in names:
        # Only finished filings: the proxy writes tmp+replace, so a
        # "*.json.tmp" mid-write filing is skipped until renamed.
        if not fn.endswith(".json"):
            continue
        aid = fn[:-len(".json")]
        if not _INGEST_AID_RE.match(aid):
            _upload_fail(d, f"pending/{fn}: aid fails the aid shape — "
                            "skipped", redact=(token,))
            failed += 1
            continue
        path = os.path.join(pending, fn)
        # Finding 50 (B1): the writer is the file's owner, never an
        # argument — a box-owned dir does not prove each file inside it
        # is box-written. Check immediately before the read to narrow
        # the check-then-use window to what ingest already accepts.
        fowner = _ingest_file_owner(path)
        if fowner not in ("bdrive", "swapd"):
            _upload_fail(d, f"pending/{fn}: owned by {fowner!r} — "
                            "refusing to upload (writer identity must be "
                            "the box, never the agent)", redact=(token,))
            failed += 1
            continue
        try:
            rec = _read_json_file(path)
        except (OSError, ValueError) as e:
            _upload_fail(d, f"pending/{fn}: unreadable ({e}) — skipped",
                         redact=(token,))
            failed += 1
            continue
        if not isinstance(rec, dict):
            _upload_fail(d, f"pending/{fn}: not an object — skipped",
                         redact=(token,))
            failed += 1
            continue
        if _ingest_item_expired(rec):
            # Locally dead already; the expiry reap will move it to
            # consumed/. Not a failure — the next tick will not see it.
            skipped += 1
            continue
        state, _note = _upload_one(d, box_id, token, url, aid, rec)
        if state == "uploaded":
            uploaded += 1
        elif state == "deduped":
            deduped += 1
        elif state == "abort":
            return 1
        else:
            failed += 1
    if failed:
        _upload_say(f"pass finished with failures: {uploaded} uploaded, "
                    f"{deduped} already on the plane, {skipped} expired, "
                    f"{failed} failed — will retry at the next cron tick",
                    redact=(token,))
        return 1
    _upload_say(f"pass complete: {uploaded} uploaded, {deduped} already "
                f"on the plane, {skipped} expired")
    return 0


def cmd_upload_filings(args):
    """Box: scan confirm/pending/ and upload new filings to the plane's
    box-authenticated file endpoint (cron-friendly: exit 0 only when
    every pending filing was uploaded or deduped, loud on failure,
    quiet-ish on success)."""
    d = _state_dir(args)
    enroll_path = os.path.join(d, "enrollment.json")
    try:
        enroll = _read_json_file(enroll_path)
    except (OSError, ValueError) as e:
        _upload_fail(d, f"enrollment.json is unreadable ({e}) — run "
                        "`request` + `redeem` first")
        return 1
    if not isinstance(enroll, dict):
        _upload_fail(d, "enrollment.json is not an object — run `request` "
                        "+ `redeem` first")
        return 1
    box_id, token = enroll.get("box_id"), enroll.get("token")
    if not box_id or not token:
        _upload_fail(d, "enrollment.json is missing box_id/token — run "
                        "`request` + `redeem` first")
        return 1
    control, msg = _resolve_control(args, enroll)
    if control is None:
        _upload_fail(d, msg)
        return 1
    approvals = _approvals_dir()
    if not os.path.isdir(approvals):
        _upload_fail(d, f"approvals dir {approvals} is missing — is "
                        "confirmd installed on this box?", redact=(token,))
        return 1
    # Serialize overlapping cron ticks: two uploaders racing the same
    # pending store would double-POST (the plane dedupes on (box_id, aid),
    # so the cost is load, not duplicates — keep it serial anyway).
    lock_path = os.path.join(d, _UPLOAD_FILINGS_LOCK_FILE)
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        # 0600 at creation is not enough: a pre-existing lock file keeps
        # its wider mode through the open. Force it every time (#883).
        os.fchmod(lock_fd, 0o600)
    except OSError as e:
        _upload_fail(d, f"upload-filings FAILED: cannot open lock file "
                        f"({e}) — check state-dir permissions",
                     redact=(token,))
        return 1
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        return _upload_filings(d, approvals, box_id, token, control)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


# ---- #959 S5a + #976 S5b: box-side WSS phone-home client -----------------------
# The persistent outbound channel from the box to the control plane, per
# docs/PHONE_HOME_WIRE_PROTOCOL.md (the S3 contract, #941). S5a is the
# connection core: stdlib-only RFC 6455 framing, the upgrade
# handshake (no redirect-following by construction, box Bearer <redacted> in
# the Authorization header only — never in a frame, never in a log),
# the durable generation fence (§5), the close-code reconnect policy
# (§6), keepalive (§4), and the upgrade-401 rotate-once path (§2).
#
# S5b (#976) adds the command-carrying half on top of the session:
# `command` frames (wire-spec §3.3 shape) dispatch into the #874 ingest
# executor with the same execute-before-ack / dedupe-by-(box_id, seq)
# semantics as the HTTPS fetch path, and `command_ack` frames ride the
# socket (the §3.3 socket-vs-HTTPS choice, recorded in the wire doc —
# the HTTPS /commands/ack endpoint stays as the fetch path's ack; the
# DO consumes both into the same acked_watermark). The socket is a
# faster carrier for the same queue, not a second queue.
#
# Unknown/reserved frame types are logged loudly and ignored, never
# acted on, never fatal to the daemon.
#
# NOTE: the plane half (#958, one Durable Object per box) is not built
# yet — the upgrade endpoint is unserved, so expect `upgrade failed`
# retries with backoff until it lands. Validated against a stub harness
# only (pairing/test_phone_home.py); live-plane acceptance is #960.
#
# Liveness: the #864 heartbeat stays the ONLY liveness signal (spec §8).
# This client never writes last_heartbeat.json; a socket the plane
# accepted is not proof the box is healthy.

_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
_WS_MAX_FRAME = 1 << 20  # 1 MiB: command payloads are <=16 KiB; bigger is a plane bug
_WS_PING_INTERVAL = 30  # spec §4: the box sends ping every 30 s
_WS_PONG_TIMEOUT = 90  # spec §4: no pong within 90 s of a ping → dead socket
_WS_BACKOFF_INITIAL = 1.0  # spec §10: 1 s initial, doubling, 60 s cap, ±25% jitter
_WS_BACKOFF_CAP = 60.0
_WS_GOING_AWAY_WAIT = 60.0  # spec §6: going-away → wait ≥ 60 s
_WS_READ_TIMEOUT = 5  # socket read quantum: keeps the ping timer + stop flag live
_WS_UPGRADE_TIMEOUT = 30  # explicit handshake deadline (create_connection's
# timeout lingers on the socket; naming it here so a future refactor
# can't silently drop the bound)
_WS_GENERATION_FILE = "phone_home_generation.json"
# Wire-spec §3.1 control class: these JSON text frames MUST be ≤ 4 KB.
_WS_CONTROL_TYPES = frozenset(
    ["hello", "welcome", "ping", "pong", "close", "command_ack"])
# Wire-spec §3.3: a command frame's payload is ≤ 16 KiB, verbatim. A
# bigger payload is a plane bug: reject the frame (log loudly, never
# ack) rather than executing unbounded work off the socket.
_WS_COMMAND_PAYLOAD_MAX = 16 * 1024

# Module-level sleep so tests can observe/stub timing without waiting out
# real backoffs.
_ws_sleep = time.sleep
# Set by the SIGTERM/SIGINT handler; the session loop polls it.
_PHONE_HOME_STOP = False


class _WsError(Exception):
    """A phone-home failure with a clean, loud message (no traceback)."""


class _WsTransportLost(_WsError):
    """TCP/TLS dropped, EOF mid-frame, or pong timeout — reconnect per policy."""


class _WsProtocolError(_WsError):
    """Wire violation (bad accept, masked server frame, undecodable frame).
    Never auto-reconnect: a protocol bug looping is a reconnect storm."""


class _WsUpgradeFailed(_WsError):
    """The upgrade did not complete (non-101, redirect, bad accept)."""


class _WsUpgradeAuth(_WsUpgradeFailed):
    """The upgrade got HTTP 401: the box token is dead per the plane."""


def _phone_home_say(d, msg, token=()):
    """Loud info channel: stdout + phone_home.log, token redacted from both.

    Mirrors _fail's redaction discipline; frames never carry the token by
    construction, but a hostile plane's close `reason` is echoed here, so
    the redact pass stays."""
    if isinstance(token, str):
        token = (token,)
    for secret in token:
        if secret:
            msg = msg.replace(secret, "<redacted>")
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} phone-home: {msg}"
    print(line)
    try:
        with open(os.path.join(d, "phone_home.log"), "a") as f:
            f.write(line + "\n")
    except OSError:
        pass  # stdout is the loud channel; a broken log must not mask it


def _phone_home_fail(d, msg, token=()):
    _fail(d, msg, redact=(token,) if isinstance(token, str) else token,
          tag="phone-home", log="phone_home.log")


# -- RFC 6455 framing (client side) -------------------------------------------
# Client→server frames are always masked (§5.3); server→client frames MUST
# arrive unmasked (§5.1) — a masked server frame is a protocol error.

def _ws_encode_frame(opcode, payload=b"", fin=True):
    b0 = (0x80 if fin else 0) | (opcode & 0x0F)
    n = len(payload)
    mask = os.urandom(4)
    if n < 126:
        header = bytes([b0, 0x80 | n])
    elif n < 65536:
        header = bytes([b0, 0x80 | 126]) + struct.pack(">H", n)
    else:
        header = bytes([b0, 0x80 | 127]) + struct.pack(">Q", n)
    masked = bytes(c ^ mask[i % 4] for i, c in enumerate(payload))
    return header + mask + masked


class _WsReader:
    """Buffered socket reader for the session.

    recv-based, deliberately NOT socket.makefile: after a read timeout a
    makefile poisons itself ("cannot read from timed out object") while
    raw recv keeps working — and this client relies on read timeouts as
    the keepalive timer's wake-up quantum. Leftover bytes from the HTTP
    upgrade read stay in the buffer, so no frame byte is ever lost."""

    def __init__(self, sock, initial=b""):
        self.sock = sock
        self.buf = bytearray(initial)

    def read_exact(self, n):
        while len(self.buf) < n:
            try:
                chunk = self.sock.recv(65536)
            except socket.timeout:
                raise  # the session loop turns the quantum into a timer tick
            if not chunk:
                raise _WsTransportLost("connection closed mid-frame")
            self.buf += chunk
        out = bytes(self.buf[:n])
        del self.buf[:n]
        return out

    def readline(self, limit=4096):
        while True:
            idx = self.buf.find(b"\n")
            if idx >= 0:
                line = bytes(self.buf[:idx + 1])
                del self.buf[:idx + 1]
                return line
            if len(self.buf) > limit:
                raise _WsUpgradeFailed("upgrade header line too long")
            try:
                chunk = self.sock.recv(4096)
            except socket.timeout:
                raise _WsUpgradeFailed("upgrade timed out")
            if not chunk:
                raise _WsUpgradeFailed("connection closed during upgrade")
            self.buf += chunk


def _ws_decode_frame(reader):
    """Read one server→client frame. Returns (opcode, payload, fin).

    Raises _WsTransportLost on EOF/timeout-drop, _WsProtocolError on a
    masked server frame, oversized frame, or a fragmented control frame.
    Control-frame payloads are capped at 125 bytes per §5.5.
    """
    hdr = reader.read_exact(2)
    b0, b1 = hdr[0], hdr[1]
    fin = bool(b0 & 0x80)
    rsv = b0 & 0x70
    opcode = b0 & 0x0F
    if rsv:
        raise _WsProtocolError("server frame has RSV bits set "
                               "(no extensions negotiated)")
    if b1 & 0x80:
        raise _WsProtocolError("server sent a masked frame")
    n = b1 & 0x7F
    if n == 126:
        n = struct.unpack(">H", reader.read_exact(2))[0]
    elif n == 127:
        n = struct.unpack(">Q", reader.read_exact(8))[0]
    if opcode in (0x8, 0x9, 0xA):
        if not fin:
            raise _WsProtocolError("fragmented control frame")
        if n > 125:
            raise _WsProtocolError("control frame payload exceeds 125 bytes")
    if n > _WS_MAX_FRAME:
        raise _WsProtocolError(f"frame too large ({n} bytes)")
    return opcode, reader.read_exact(n), fin


def _ws_send_json(sock, obj):
    payload = json.dumps(obj, separators=(",", ":")).encode()
    sock.sendall(_ws_encode_frame(0x1, payload))


def _ws_read_json_frame(reader):
    """Read frames until a complete text message arrives. Returns the
    decoded object. Binary messages are a protocol error (JSON text
    frames only, §3); continuation frames are reassembled.

    The reassembled total is capped at _WS_MAX_FRAME: the per-frame cap
    in _ws_decode_frame does not bound a hostile plane's continuation
    count, and an unbounded join would OOM the daemon. Control-class
    frames (spec §3.1) are additionally capped at 4 KB."""
    parts = []
    total = 0
    while True:
        opcode, payload, fin = _ws_decode_frame(reader)
        if opcode == 0x2:
            raise _WsProtocolError("binary frame (JSON text frames only)")
        if opcode == 0x0:
            if not parts:
                raise _WsProtocolError("continuation with nothing to continue")
        elif opcode == 0x1:
            if parts:
                raise _WsProtocolError(
                    "new message inside fragmentation (RFC 6455 §5.4)")
        elif opcode == 0x9:
            # WS-level ping: answer with a WS-level pong per RFC 6455.
            # (The wire spec's keepalive is the JSON ping/pong control
            # frames; either layer may ping.)
            raise _WsPing(payload)
        elif opcode == 0xA:
            raise _WsPong(payload)
        elif opcode == 0x8:
            # Transport-level close with no control frame: no protocol
            # meaning (spec §6) — the session is simply gone.
            raise _WsTransportLost("peer closed the websocket")
        else:
            raise _WsProtocolError(f"unknown opcode {opcode:#x}")
        parts.append(payload)
        total += len(payload)
        if total > _WS_MAX_FRAME:
            raise _WsProtocolError(
                "reassembled message exceeds the frame cap")
        if fin:
            break
    try:
        obj = json.loads(b"".join(parts).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, RecursionError) as e:
        raise _WsProtocolError(f"undecodable text frame: {e}")
    if total > 4096 and isinstance(obj, dict) \
            and obj.get("type") in _WS_CONTROL_TYPES:
        raise _WsProtocolError("control frame exceeds 4 KB (spec §3.1)")
    return obj


class _WsPing(Exception):
    def __init__(self, payload):
        self.payload = payload


class _WsPong(Exception):
    def __init__(self, payload):
        self.payload = payload


# -- Upgrade handshake ----------------------------------------------------------

def _ws_url_for_control(control):
    """Derive the wss:// (or loopback ws://) URL root from a validated
    control URL. _resolve_control already failed closed on non-loopback
    http://, so a ws:// result here is loopback-only by construction."""
    u = urllib.parse.urlparse(control)
    scheme = {"https": "wss", "http": "ws"}[u.scheme]
    return urllib.parse.urlunparse(
        (scheme, u.netloc, u.path.rstrip("/"), "", "", ""))


def _ws_upgrade(host, port, use_tls, path):
    """Open the raw socket, do TLS, and speak the HTTP/1.1 upgrade by hand.

    No redirect-following exists on this path by construction (spec §2:
    any 3xx is an upgrade failure, never followed — a redirect-following
    client could forward the Authorization header cross-origin).
    Returns the connected socket; the caller runs _ws_do_handshake next.
    """
    try:
        raw = socket.create_connection((host, port), timeout=30)
    except OSError as e:
        raise _WsUpgradeFailed(f"TCP connect failed: {e}")
    try:
        if use_tls:
            sock = ssl.create_default_context().wrap_socket(
                raw, server_hostname=host)
        else:
            sock = raw
    except (OSError, ssl.SSLError) as e:
        try:
            raw.close()
        except OSError:
            pass
        raise _WsUpgradeFailed(f"TLS handshake failed: {e}")
    return sock


def _ws_do_handshake(sock, host, path, key, token):
    """Send the upgrade request and validate the 101 response.

    Returns the _WsReader on success (it may already hold frame bytes read
    past the headers); raises _WsUpgradeAuth on 401, _WsUpgradeFailed
    otherwise. Never logs the request (it carries the bearer)."""
    req = (f"GET {path} HTTP/1.1\r\n"
           f"Host: {host}\r\n"
           f"Authorization: Bearer {token}\r\n"
           "Upgrade: websocket\r\n"
           "Connection: Upgrade\r\n"
           f"Sec-WebSocket-Key: {key}\r\n"
           "Sec-WebSocket-Version: 13\r\n"
           f"User-Agent: {USER_AGENT}\r\n\r\n")
    reader = _WsReader(sock)
    # Explicit handshake deadline: create_connection's timeout lingers on
    # the socket, but pin it by name so the bound is visible here.
    sock.settimeout(_WS_UPGRADE_TIMEOUT)
    try:
        sock.sendall(req.encode())
        status_line = reader.readline().decode("latin-1")
        headers = {}
        while True:
            line = reader.readline().decode("latin-1")
            if line in ("\r\n", "\n", ""):
                break
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()
    except _WsUpgradeFailed:
        raise
    except (OSError, socket.timeout) as e:
        raise _WsUpgradeFailed(f"upgrade I/O failed: {e}")
    parts = status_line.split()
    if len(parts) < 2 or not parts[1].isdigit():
        raise _WsUpgradeFailed("malformed upgrade status line")
    status = int(parts[1])
    if status == 401:
        raise _WsUpgradeAuth("plane rejected the box token (HTTP 401)")
    if status in (301, 302, 303, 307, 308):
        raise _WsUpgradeFailed(
            f"plane redirected the upgrade (HTTP {status}) — refusing: "
            "the Authorization header must never be forwarded cross-origin")
    if status != 101:
        raise _WsUpgradeFailed(f"upgrade failed (HTTP {status})")
    accept = headers.get("sec-websocket-accept", "")
    expect = base64.b64encode(
        hashlib.sha1((key + _WS_GUID).encode()).digest()).decode()
    if accept != expect:
        raise _WsUpgradeFailed("bad Sec-WebSocket-Accept (possible MITM)")
    return reader


# -- Durable generation (§5) -----------------------------------------------------

def _phone_home_claim_generation(d):
    """Claim the next generation, crash-safe.

    Reads the last persisted generation, persists last+1 via temp+rename,
    and returns (generation, status) with status in "ok" | "first-run" |
    "counter-loss". The persist happens BEFORE the value is used: a crash
    between persist and use skips a value, never reuses one — which is
    what the DO's generation fence needs. A corrupt/missing file can only
    report counter-loss; the DO's stale-generation close is the recovery
    path (adopt last_generation+1), so a lost counter can never fence a
    live session by replaying an old value.
    """
    path = os.path.join(d, _WS_GENERATION_FILE)
    last, usable, existed = None, False, False
    try:
        with open(path) as f:
            data = json.load(f)
        existed = True
        if (isinstance(data, dict)
                and isinstance(data.get("generation"), int)
                and not isinstance(data.get("generation"), bool)
                and data["generation"] >= 0):
            last, usable = data["generation"], True
    except (OSError, ValueError):
        try:
            existed = os.path.exists(path)
        except OSError:
            existed = False
    nxt = (last + 1) if usable else 1
    tmp = path + ".tmp"
    try:
        _write_private(tmp, json.dumps({"generation": nxt}).encode())
        os.replace(tmp, path)
    except OSError as e:
        # A wedged state dir (disk full, permissions) is a loud local
        # failure, not a traceback and not a reconnect loop.
        raise _WsError(f"generation file unwritable ({e})")
    if usable:
        return nxt, "ok"
    return nxt, ("counter-loss" if existed else "first-run")


def _phone_home_adopt_generation(d, generation):
    """Persist a DO-dictated generation (stale-generation recovery)."""
    path = os.path.join(d, _WS_GENERATION_FILE)
    tmp = path + ".tmp"
    try:
        _write_private(tmp, json.dumps({"generation": generation}).encode())
        os.replace(tmp, path)
    except OSError as e:
        raise _WsError(f"generation file unwritable ({e})")


def _phone_home_bump_epoch(d):
    """Counter loss is a reboot-equivalent (§5): claim a higher epoch so
    stale in-flight commands die per #848's incarnation rule.

    Only touches an existing, parseable cursor file; a missing cursor
    means no in-flight state to fence, so there is nothing to bump.
    Plain reconnects never call this."""
    path = os.path.join(d, _INGEST_CURSOR_FILE)
    try:
        with open(path) as f:
            cur = json.load(f)
    except (OSError, ValueError):
        return False
    if not isinstance(cur, dict):
        return False
    epoch = cur.get("epoch")
    if not isinstance(epoch, int) or isinstance(epoch, bool):
        epoch = 0
    cur["epoch"] = epoch + 1
    try:
        _write_private(path, json.dumps(cur, indent=2).encode())
    except OSError as e:
        raise _WsError(f"cursor file unwritable ({e})")
    return True


# -- Close-code reconnect policy (spec §6) ----------------------------------------

# Each entry: (action, param). Actions:
#   "reconnect" — open a new session (param: delay seconds, None = backoff)
#   "adopt"     — persist param as the generation, bump epoch, reconnect now
#   "exit"      — leave the daemon (param: exit code)
def _phone_home_close_action(code, frame):
    if code == "revoked":
        # No reconnect loop — the heartbeat cron's 401 prints the re-pair
        # guidance; re-pair is the human path.
        return ("exit", 1)
    if code == "expired":
        # Reconnect with the CURRENT token (a post-rotation socket riding
        # the previous token lands here when the 15-min grace lapses — do
        # NOT rotate again); the caller re-reads enrollment first.
        return ("reconnect", 0)
    if code == "superseded-generation":
        # Our only socket got superseded, but we hold the process flock —
        # a second local instance cannot exist. A concurrent session under
        # our identity is a token-theft signal: fail closed and loud.
        return ("exit", 1)
    if code == "stale-generation":
        lg = frame.get("last_generation") if isinstance(frame, dict) else None
        if isinstance(lg, int) and not isinstance(lg, bool) and lg >= 0:
            return ("adopt", lg + 1)
        return ("exit", 1)  # malformed: cannot adopt safely
    if code in ("identity-mismatch", "protocol-error"):
        return ("exit", 1)  # bug — never auto-reconnect
    if code == "going-away":
        return ("reconnect", _WS_GOING_AWAY_WAIT)  # ≥ 60 s, backoff reset
    return ("exit", 1)  # unknown close code: fail closed, no reconnect


def _ws_backoff_delay(attempt, rng=random.random):
    """1 s initial, doubling, 60 s cap, ±25% jitter (spec §10).

    The exponent is capped: beyond 2**6 the 60 s cap dominates anyway,
    and an unbounded bigint would OverflowError the float multiply after
    ~1024 consecutive failures. Jitter applies before the final cap, so
    the result never exceeds 60 s."""
    raw = _WS_BACKOFF_INITIAL * (2 ** min(attempt, 6))
    return min(_WS_BACKOFF_CAP, raw * (0.75 + 0.5 * rng()))


def _ws_sleep_or_stop(seconds):
    """Sleep in ≤1 s quanta so SIGTERM/SIGINT stops the daemon promptly.

    Returns True when the stop flag was set mid-sleep (the caller should
    break out to the clean shutdown path). Quantum-counted, not
    clock-counted: deterministic under a stubbed _ws_sleep in tests."""
    while seconds > 0:
        if _PHONE_HOME_STOP:
            return True
        quantum = min(1.0, seconds)
        _ws_sleep(quantum)
        if _PHONE_HOME_STOP:
            return True
        seconds -= quantum
    return False


# -- Session ----------------------------------------------------------------------

class _PhoneHomeSession:
    """One connected WSS session: hello/welcome, keepalive, frame dispatch.

    S5b (#976): the session also carries the socket half of the durable
    command queue — `command` frames dispatch into the #874 ingest
    executor and `command_ack` frames ride the socket (the §3.3 decision,
    recorded in docs/PHONE_HOME_WIRE_PROTOCOL.md). The socket is a faster
    carrier for the same queue, not a second queue: redeliveries dedupe
    through the shared backstops (the ingested idempotency log and the
    consumed/ O_EXCL records), and the acked prefix never skips a bad
    row — the same never-advance-past-unacked invariant the HTTPS fetch
    path's cursor enforces.
    """

    def __init__(self, d, sock, reader, box_id, generation, token,
                 approvals=None):
        self.d = d
        self.sock = sock
        self.reader = reader
        self.box_id = box_id
        self.generation = generation
        self.token = token
        # Production always passes the resolved dir; the default keeps
        # direct unit construction (which never handles commands) working.
        self.approvals = approvals if approvals is not None \
            else _approvals_dir()
        self.welcomed = False
        # Highest contiguously socket-acked seq on THIS session. The DO's
        # acked_watermark is the durable record; this is the per-session
        # ordering guard so a malformed or failed row holds the queue
        # (later seqs wait for the re-drive) instead of being skipped.
        self._acked_prefix = None
        # Shared with the HTTPS ingest path: redelivery dedupe by
        # (box_id, seq) survives a session boundary through this log and
        # the consumed/ records, not through _acked_prefix.
        self._ingested = _load_ingested(d) if d is not None else {}

    def send(self, obj):
        try:
            _ws_send_json(self.sock, obj)
        except OSError as e:
            # The peer died between reads: a send-side EPIPE/RST is the
            # same transport loss as a read-side EOF, not a traceback.
            raise _WsTransportLost(f"send failed: {e}")

    def _socket_ack(self, seq, epoch):
        """Send the wire-spec §3.1 command_ack for one executed command.

        The ack carries this session's generation: it is bound to the
        fence that received the command, so the DO can reject acks from
        a stale session the same way it rejects stale commands. Raises
        _WsTransportLost when the socket died mid-send."""
        ack = {"type": "command_ack", "generation": self.generation,
               "seq": seq}
        if isinstance(epoch, int) and not isinstance(epoch, bool):
            ack["epoch"] = epoch
        self.send(ack)

    def _handle_socket_command(self, frame):
        """Execute one `command` frame via the #874 ingest executor.

        Returns "ok" when the frame was handled (acked, or deliberately
        not acked) and "transport-lost" when the ack could not be sent —
        the caller reconnects and the command redelivers; the
        idempotency backstops make the re-execution safe. A frame the
        box cannot trust is logged loudly and never acked: the DO
        re-drives from its acked_watermark, the same noisy-until-fixed
        posture as the HTTPS path's malformed-row skip.
        """
        if frame.get("generation") != self.generation:
            # A stale session's frame (or a plane bug): it does not
            # belong to this fence. Never execute, never ack.
            _phone_home_say(
                self.d,
                "ignoring command frame for generation "
                f"{_plane_text(frame.get('generation'))!r} (session is "
                f"{self.generation}) — stale or misaddressed",
                self.token)
            return "ok"
        inner = frame.get("payload")
        if not isinstance(inner, dict):
            _phone_home_say(self.d,
                            "ignoring command frame with non-object "
                            "payload (plane bug) — not acked, will "
                            "re-drive",
                            self.token)
            return "ok"
        try:
            payload_bytes = len(json.dumps(inner).encode("utf-8"))
        except (TypeError, ValueError):
            payload_bytes = _WS_COMMAND_PAYLOAD_MAX + 1
        if payload_bytes > _WS_COMMAND_PAYLOAD_MAX:
            _phone_home_say(
                self.d,
                f"ignoring command frame: payload {payload_bytes} bytes "
                "exceeds the wire-spec 16 KiB bound (plane bug) — not "
                "acked, will re-drive",
                self.token)
            return "ok"
        shaped = _ingest_command_shape({
            "seq": frame.get("seq"), "epoch": frame.get("epoch"),
            "kind": inner.get("kind"), "payload": inner.get("payload")})
        if shaped is None:
            # No seq to ack and nothing safe to execute: the DO
            # re-drives until the plane fixes the row — noisy, but the
            # alternative (advancing past it) hides a plane bug. Mirrors
            # the HTTPS path's malformed-row skip.
            _phone_home_say(self.d,
                            "ignoring malformed command frame (plane "
                            "bug) — not acked, will re-drive",
                            self.token)
            return "ok"
        seq, kind, payload, epoch = shaped
        if self._acked_prefix is not None:
            if seq <= self._acked_prefix:
                # Redelivery of an already-acked seq (a lost ack heals
                # this way): re-ack without re-executing.
                self._socket_ack(seq, epoch)
                return "ok"
            if seq > self._acked_prefix + 1:
                # Gap: the DO drives in order from its watermark, so a
                # jump means a row is missing or was rejected. Hold the
                # prefix — the re-drive resends the gap; acking past it
                # would hide a plane bug the way skipping a bad row
                # would.
                _phone_home_say(
                    self.d,
                    f"ignoring command seq={seq}: gap after acked "
                    f"prefix {self._acked_prefix} — not acked, waiting "
                    "on the re-drive",
                    self.token)
                return "ok"
        attention = []
        try:
            if kind not in _HONORED_COMMAND_KINDS:
                # The plane is opaque to kinds and the box executor
                # decides; ack-and-log keeps one unknown kind from
                # wedging the queue. `kind` is plane-controlled: scrub
                # it like any plane string on a loud channel.
                _phone_home_say(
                    self.d,
                    f"seq={seq}: unknown command kind "
                    f"{_plane_text(kind)!r} — acked without execution",
                    self.token)
                consumed = True
            elif kind == "approval_decision":
                consumed = _ingest_approval_decision(
                    self.d, self.approvals, self.box_id, self.token, seq,
                    payload, self._ingested, attention)
            else:  # pragma: no cover — registry and branch above stay in sync
                consumed = False
        except (OSError, ValueError) as e:
            # A local I/O failure (disk full, torn state) must fail
            # closed with a loud log — never a traceback, and never an
            # ack: the command redelivers on the next (re)bind.
            _phone_home_say(self.d,
                            f"seq={seq}: local failure during socket "
                            f"ingest ({e}) — not acked, will re-drive",
                            self.token)
            return "ok"
        for note in attention:
            _phone_home_say(self.d, "ATTENTION: " + note, self.token)
        if not consumed:
            return "ok"  # not acked; the DO re-drives
        try:
            _save_ingested(self.d, self._ingested)
        except OSError as e:
            _phone_home_say(self.d,
                            f"seq={seq}: ingested-log save failed ({e}) "
                            "— not acked; redelivery is idempotent, will "
                            "re-drive",
                            self.token)
            return "ok"
        try:
            self._socket_ack(seq, epoch)
        except _WsTransportLost:
            # Executed and logged, but the ack never left: the command
            # redelivers and the backstops dedupe it. Reconnect now.
            return "transport-lost"
        self._acked_prefix = seq
        _phone_home_say(self.d,
                        f"acked command seq={seq} "
                        f"(kind={_plane_text(kind)!r}) over the socket",
                        self.token)
        return "ok"

    def run(self):
        """Returns ("closed", code, frame) | ("transport-lost",) | ("bug", msg)."""
        try:
            return self._run()
        except _WsTransportLost:
            # Send-side EPIPE/RST (hello, ping, pong) is the same
            # transport loss as a read-side EOF.
            return ("transport-lost",)

    def _run(self):
        self.send({"type": "hello", "box_id": self.box_id,
                   "generation": self.generation})
        try:
            welcome = _ws_read_json_frame(self.reader)
        except _WsTransportLost:
            return ("transport-lost",)
        except socket.timeout:
            # A slow plane (DO cold start) is a transport stall like any
            # other: back off and reconnect, never traceback.
            return ("transport-lost",)
        except (_WsProtocolError, _WsPing, _WsPong) as e:
            return ("bug", f"no valid welcome before the socket died ({e})")
        if isinstance(welcome, dict) and welcome.get("type") == "close":
            # A close answering hello is not a welcome failure: the spec
            # mandates close/stale-generation here (§5), and a pre-welcome
            # revoked deserves the re-pair guidance, not a "bug" message.
            # Route it through the close table like any other close.
            return ("closed", welcome.get("code"), welcome)
        if (not isinstance(welcome, dict)
                or welcome.get("type") != "welcome"
                or welcome.get("box_id") != self.box_id
                or welcome.get("accepted_generation") != self.generation):
            return ("bug",
                    "bad welcome (identity or generation mismatch) — "
                    "not reconnecting")
        self.welcomed = True
        _phone_home_say(
            self.d,
            f"channel open (generation {self.generation}, "
            f"server_time {_plane_text(welcome.get('server_time'))})",
            self.token)
        next_ping_at = time.monotonic() + _WS_PING_INTERVAL
        ping_sent_at = None
        while not _PHONE_HOME_STOP:
            now = time.monotonic()
            if ping_sent_at is not None and \
                    now - ping_sent_at > _WS_PONG_TIMEOUT:
                return ("transport-lost",)
            if now >= next_ping_at:
                self.send({"type": "ping", "generation": self.generation,
                           "ts": int(time.time())})
                ping_sent_at = now
                next_ping_at = now + _WS_PING_INTERVAL
            try:
                frame = _ws_read_json_frame(self.reader)
            except socket.timeout:
                continue
            except _WsTransportLost as e:
                return ("transport-lost",)
            except _WsProtocolError as e:
                return ("bug", f"protocol error: {e}")
            except _WsPing as e:
                # WS-level ping: RFC 6455 pong (control payload ≤125).
                try:
                    self.sock.sendall(
                        _ws_encode_frame(0xA, e.payload[:125]))
                except OSError:
                    return ("transport-lost",)
                continue
            except _WsPong:
                ping_sent_at = None
                continue
            if not isinstance(frame, dict):
                _phone_home_say(self.d,
                                "ignoring non-object frame from the plane",
                                self.token)
                continue
            ftype = frame.get("type")
            if ftype == "ping":
                # Spec keepalive: answer promptly, echo the generation+ts.
                self.send({"type": "pong", "generation": self.generation,
                           "ts": frame.get("ts")})
            elif ftype == "pong":
                ping_sent_at = None
            elif ftype == "close":
                return ("closed", frame.get("code"), frame)
            elif ftype == "welcome":
                _phone_home_say(self.d, "ignoring duplicate welcome",
                                self.token)
            elif ftype == "command":
                # S5b (#976): socket command frames dispatch into the
                # #874 ingest executor and ack over the socket (§3.3).
                if self._handle_socket_command(frame) == "transport-lost":
                    return ("transport-lost",)
            elif ftype == "command_ack":
                # box→DO only (§3.1): a DO sending one is a plane bug —
                # log it loudly, never act on it.
                _phone_home_say(
                    self.d,
                    "ignoring command_ack frame from the plane "
                    "(box→DO only — plane bug)",
                    self.token)
            else:
                _phone_home_say(
                    self.d,
                    f"ignoring unknown frame type "
                    f"{_plane_text(ftype)!r} (never acted on)",
                    self.token)
        return ("stopped",)


def _phone_home_request_stop(signum, frame):
    global _PHONE_HOME_STOP
    _PHONE_HOME_STOP = True


# -- Connect + daemon ---------------------------------------------------------------

def _phone_home_connect(d, box_id, token, control, generation):
    """Upgrade and run one session. Returns (outcome, welcomed)."""
    ws_root = _ws_url_for_control(control)
    u = urllib.parse.urlparse(ws_root)
    host, port = u.hostname, u.port or (443 if u.scheme == "wss" else 80)
    path = (u.path + "/v1/boxes/" + urllib.parse.quote(box_id, safe="")
            + "/phone-home")
    _phone_home_say(d,
                    f"connecting (generation {generation}) to "
                    f"{_scrub_url_userinfo(ws_root)}"
                    "/v1/boxes/.../phone-home",
                    token)
    sock = _ws_upgrade(host, port, u.scheme == "wss", path)
    try:
        key = base64.b64encode(os.urandom(16)).decode()
        reader = _ws_do_handshake(sock, u.netloc.split("@")[-1], path,
                                   key, token)
    except Exception:
        sock.close()
        raise
    sock.settimeout(_WS_READ_TIMEOUT)
    session = _PhoneHomeSession(d, sock, reader, box_id, generation, token,
                                _approvals_dir())
    try:
        return session.run(), session.welcomed
    finally:
        try:
            sock.close()
        except OSError:
            pass


def _phone_home_rotate_once(args, d, enroll_path):
    """One rotate attempt for the upgrade-401 path (spec §2).

    Reuses cmd_rotate's full machinery (proof-of-possession, locks, loud
    messages, expiry validation). Returns the new token on success, None
    on failure — cmd_rotate already printed the right guidance for each
    failure class (401 → re-pair, 403 → clock skew)."""
    fake = argparse.Namespace(auto=False, within=AUTO_ROTATE_WITHIN,
                              dir=args.dir, control=args.control)
    if cmd_rotate(fake) != 0:
        return None
    try:
        enroll = _read_json_file(enroll_path)
    except (OSError, ValueError):
        return None
    new_token = enroll.get("token") if isinstance(enroll, dict) else None
    return new_token or None


def _phone_home_read_enrollment(d, enroll_path):
    try:
        enroll = _read_json_file(enroll_path)
    except (OSError, ValueError) as e:
        return None, (f"enrollment.json is unreadable ({e}) — "
                      "run `request` + `redeem` first")
    if not isinstance(enroll, dict):
        return None, ("enrollment.json is not an object — "
                      "run `request` + `redeem` first")
    box_id, token = enroll.get("box_id"), enroll.get("token")
    if not isinstance(box_id, str) or not box_id \
            or not isinstance(token, str) or not token:
        return None, ("enrollment.json is missing box_id/token — "
                      "run `request` + `redeem` first")
    return enroll, None


def cmd_phone_home(args):
    d = _state_dir(args)
    enroll_path = os.path.join(d, "enrollment.json")
    enroll, err = _phone_home_read_enrollment(d, enroll_path)
    if enroll is None:
        _phone_home_fail(d, err)
        return 1
    box_id, token = enroll["box_id"], enroll["token"]
    control, msg = _resolve_control(args, enroll)
    if control is None:
        _phone_home_fail(d, msg, token)
        return 1
    # The generation counter must have exactly one writer: a second
    # daemon would fork the counter and fence its own live session.
    lock_path = os.path.join(d, ".phone-home.lock")
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        # 0600 at creation is not enough: a pre-existing lock file keeps
        # its wider mode through the open. Force it every time (#883).
        os.fchmod(lock_fd, 0o600)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        _phone_home_fail(d, "another phone-home instance holds the lock — "
                            "not starting a second one", token)
        return 1
    global _PHONE_HOME_STOP
    _PHONE_HOME_STOP = False
    try:
        signal.signal(signal.SIGTERM, _phone_home_request_stop)
        signal.signal(signal.SIGINT, _phone_home_request_stop)
    except (OSError, ValueError):
        pass  # non-POSIX or embedded: the loop still exits on close codes
    # Defense in depth: phone_home.log carries redacted plane strings;
    # keep it 0600 like the other state files even though the token never
    # lands here unredacted (Security nit).
    try:
        _log_fd = os.open(os.path.join(d, "phone_home.log"),
                          os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
        os.fchmod(_log_fd, 0o600)
        os.close(_log_fd)
    except OSError:
        pass  # _phone_home_say degrades to stdout-only
    _phone_home_say(d, f"phone-home starting for box "
                       f"{_plane_text(box_id)} (S5a connection core + S5b "
                       "socket command frames/acks; "
                       "heartbeat stays the only liveness signal)", token)
    attempt, rotate_tried = 0, False
    pending_generation = None  # set by the stale-generation adopt path
    try:
        while not _PHONE_HOME_STOP:
            if pending_generation is not None:
                # Adopted from the DO's stale-generation close: use it
                # verbatim (NOT claim+1 — the DO dictated this value).
                generation, gen_status = pending_generation, "adopted"
                pending_generation = None
            else:
                try:
                    generation, gen_status = _phone_home_claim_generation(d)
                except _WsError as e:
                    # Local state failure (disk full, permissions): loud,
                    # no traceback, no reconnect loop.
                    _phone_home_fail(d, f"{e}", token)
                    return 1
            if gen_status == "counter-loss":
                # Reboot-equivalent (§5): the old counter is gone, so any
                # in-flight commands from the lost incarnation must die.
                try:
                    _phone_home_bump_epoch(d)
                except _WsError as e:
                    _phone_home_fail(d, f"{e}", token)
                    return 1
                _phone_home_say(
                    d, "generation counter lost — claimed epoch+1 "
                       "(counter loss is a reboot-equivalent per §5); the "
                       "DO's stale-generation fence will correct the "
                       "generation on connect", token)
            try:
                outcome, welcomed = _phone_home_connect(
                    d, box_id, token, control, generation)
            except _WsUpgradeAuth:
                if rotate_tried:
                    _phone_home_fail(
                        d, "upgrade rejected (401) after a fresh rotate — "
                           "this box token is dead; re-pair the box "
                           "(`request` + `redeem`)", token)
                    return 1
                _phone_home_say(d, "upgrade rejected (401) — attempting one "
                                   "rotate before re-pair guidance", token)
                new_token = _phone_home_rotate_once(
                    args, d, enroll_path)
                if new_token is None:
                    return 1  # rotate printed the guidance already
                token = new_token
                rotate_tried, attempt = True, 0
                continue
            except _WsUpgradeFailed as e:
                _phone_home_fail(d, f"upgrade failed: {e} — will retry "
                                    "with backoff (HTTPS heartbeat and "
                                    "command polling continue meanwhile)",
                                 token)
                if _ws_sleep_or_stop(_ws_backoff_delay(attempt)):
                    break
                attempt += 1
                continue
            except _WsError as e:
                _phone_home_fail(d, f"phone-home error: {e} — will retry "
                                    "with backoff", token)
                if _ws_sleep_or_stop(_ws_backoff_delay(attempt)):
                    break
                attempt += 1
                continue
            if welcomed:
                # Each healthy session earns its own rotate budget: a 401
                # after a long-lived session gets a fresh rotate attempt
                # instead of immediate re-pair guidance.
                rotate_tried = False
            kind = outcome[0]
            if kind == "stopped":
                _phone_home_say(d, "stopping on signal", token)
                return 0
            if kind == "transport-lost":
                _phone_home_say(d, "socket lost — reconnecting with backoff "
                                   "(HTTPS heartbeat and command polling "
                                   "continue meanwhile)", token)
                if _ws_sleep_or_stop(_ws_backoff_delay(attempt)):
                    break
                attempt += 1
                continue
            if kind == "bug":
                _phone_home_fail(d, f"{outcome[1]} — not reconnecting "
                                    "(fix the client or the plane)", token)
                return 1
            # kind == "closed": the DO sent a close control frame.
            code, frame = outcome[1], outcome[2]
            reason = frame.get("reason") if isinstance(frame, dict) else None
            action, param = _phone_home_close_action(code, frame)
            _phone_home_say(
                d,
                f"plane closed the channel (code={_plane_text(code)}"
                f"{f', reason={_plane_text(reason)}' if reason else ''}) → "
                f"{action}", token)
            if action == "exit":
                if code == "revoked":
                    _phone_home_fail(
                        d, "box token revoked — not reconnecting (re-pair "
                           "is the human path: `request` + `redeem`); the "
                           "HTTPS heartbeat will 401 with the same guidance",
                        token)
                elif code == "superseded-generation":
                    _phone_home_fail(
                        d, "our socket was superseded by a newer generation "
                           "but this daemon holds the process lock — a "
                           "concurrent session under our identity should "
                           "not exist; not reconnecting", token)
                else:
                    _phone_home_fail(
                        d, f"unrecoverable close ({_plane_text(code)}) — "
                           "not reconnecting", token)
                return param
            if action == "adopt":
                try:
                    _phone_home_adopt_generation(d, param)
                    _phone_home_bump_epoch(d)
                except _WsError as e:
                    _phone_home_fail(d, f"{e}", token)
                    return 1
                _phone_home_say(
                    d, f"adopted generation {param} after stale-generation "
                       "fence (counter loss → epoch+1 per §5) — reconnecting",
                    token)
                pending_generation, attempt = param, 0
                # A beat before the adopt reconnect: a plane emitting
                # repeated stale-generation closes must not pin the box in
                # a zero-delay TCP+TLS reconnect loop.
                if _ws_sleep_or_stop(1.0):
                    break
                continue
            # action == "reconnect"
            if code == "expired":
                # Re-read enrollment: the rotate --auto cron may have
                # replaced the token while we rode the old one.
                enroll2, err2 = _phone_home_read_enrollment(d, enroll_path)
                if enroll2 is None:
                    _phone_home_fail(d, err2, token)
                    return 1
                token = enroll2["token"]
                exp = enroll2.get("token_expires_at")
                if isinstance(exp, int) and not isinstance(exp, bool) \
                        and exp <= int(time.time()):
                    if rotate_tried:
                        # The rotate budget is one per healthy session: a
                        # plane closing expired in a tight loop must not
                        # spin rotate → handshake → expired forever.
                        _phone_home_fail(
                            d, "token expired again after a rotate — not "
                               "rotating in a loop; re-pair the box "
                               "(`request` + `redeem`)", token)
                        return 1
                    _phone_home_say(
                        d, "no live token after expiry close — one rotate "
                           "attempt", token)
                    new_token = _phone_home_rotate_once(
                        args, d, enroll_path)
                    if new_token is None:
                        return 1
                    token = new_token
                    rotate_tried = True
            if code == "going-away":
                # Spec §6: wait ≥ 60 s. The wait itself is the backoff.
                if _ws_sleep_or_stop(param):
                    break
                attempt = 0
                continue
            # Any other server-directed reconnect (expired): back off with
            # a floor, growing on repeats — a plane emitting closes in a
            # tight loop must not pin the box in a hot reconnect cycle.
            if _ws_sleep_or_stop(_ws_backoff_delay(attempt)):
                break
            attempt += 1
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
        except OSError:
            pass
    _phone_home_say(d, "stopping on signal", token)
    return 0


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

    s = sub.add_parser("upload-filings", help="box: upload locally filed "
                                      "approvals from confirm/pending/ to "
                                      "the plane's box-authenticated file "
                                      "endpoint (cron-friendly: exit 0 only "
                                      "when every pending filing was "
                                      "uploaded or deduped, loud on "
                                      "failure)")
    s.set_defaults(fn=cmd_upload_filings)

    s = sub.add_parser("phone-home", help="box: hold the persistent "
                                      "outbound WSS phone-home channel to "
                                      "the control plane (daemon: reconnects "
                                      "per docs/PHONE_HOME_WIRE_PROTOCOL.md; "
                                      "the #864 heartbeat stays the only "
                                      "liveness signal; plane half #958 not "
                                      "built yet — expect upgrade retries)")
    s.set_defaults(fn=cmd_phone_home)

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
