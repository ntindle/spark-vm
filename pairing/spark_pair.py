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


class _RedirectAuthStripper(urllib.request.HTTPRedirectHandler):
    """urllib forwards manually-set Authorization headers across redirects —
    including to a DIFFERENT origin. On this credential-bearing client that
    is a token leak (box bearer token, owner API key): a compromised or
    misconfigured plane, or a redirect chain the box didn't expect, would
    harvest them. Strip Authorization whenever the redirect leaves the
    original origin (scheme/host/port); same-origin redirects keep it."""

    @staticmethod
    def _origin(parsed):
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        return (parsed.scheme, (parsed.hostname or "").lower(), port)

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old_origin = self._origin(urllib.parse.urlparse(req.full_url))
        new_origin = self._origin(
            urllib.parse.urlparse(urllib.parse.urljoin(req.full_url, newurl)))
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
    return False, (f"refusing cleartext http:// control plane ({control}) — "
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
        print(f"request failed: {resp.get('error', status)}")
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
    print(f"    {resp['code']}")
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
            print(f"pairing {resp.get('status', 'gone')} — run `request` again")
            return 1
        if status != 200 or not resp.get("ok"):
            print(f"status check failed: {resp.get('error', status)}")
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
        print(f"redeem failed: {resp.get('error', status)}")
        return 1
    enroll_path = os.path.join(d, "enrollment.json")
    _write_private(enroll_path, json.dumps(
        {"box_id": resp["box_id"], "token": resp["token"],
         "token_expires_at": resp["token_expires_at"],
         "control": control}, indent=2).encode())
    os.remove(pairing_path)
    print(f"enrolled as {resp['box_id']} — token saved to {enroll_path} (0600)")
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
        print(f"rotation rejected ({resp.get('error', status)}): this box "
              "token is dead (expired, revoked, or never valid) — re-pair "
              "the box (`request` + `redeem`)")
        return 1
    if status == 403:
        # Bearer <redacted> accepted but the proof was rejected: do NOT re-pair —
        # the enrollment is fine, the proof or the plane is at fault.
        print(f"rotation refused ({resp.get('error', status)}): the plane "
              "rejected the proof-of-possession signature — check the box "
              "clock (window is ±300 s) and the plane, then retry; the "
              "current token is untouched")
        return 1
    if status != 200 or not resp.get("ok") or not resp.get("token"):
        print(f"rotation failed: {resp.get('error', status)}")
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
    print(f"rotated box token for {box_id} "
          f"(proof: {resp.get('proof', 'unknown')}); new token expires {exp}")
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
        print(f"revoke failed: {resp.get('error', status)}")
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


def _fail(d, msg, redact=()):
    """Fail loud: stderr + appended to heartbeat.log in the state dir.

    `redact` lists secret values that must never reach either channel: any
    occurrence is replaced with <redacted> (defense in depth — the failure
    classes above never include the token themselves, but an error string
    echoed back by a misbehaving plane must not become a credential leak
    in a local log).
    """
    for secret in redact:
        if secret:
            msg = msg.replace(secret, "<redacted>")
    line = (f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} heartbeat FAILED: "
            f"{msg}")
    print(line, file=sys.stderr)
    try:
        with open(os.path.join(d, "heartbeat.log"), "a") as f:
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
        _fail(d, f"heartbeat rejected ({resp.get('error', status)}): this "
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
    _fail(d, f"heartbeat failed: {resp.get('error', status)} "
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
            print(f"list failed: {resp.get('error', status)}")
            return 1
        pairs = resp.get("pairings", [])
        if not pairs:
            print("no pending pairings")
            return 0
        print("Pending pairings:")
        for p in pairs:
            # The server never returns pairing codes (stored hashed);
            # match by the id the box printed at request time.
            print(f"  {p['id']}  {p['box_name']}  {p['fingerprint']}")
        print()
        pid = input("Pairing id to approve: ").strip()
    if not pid:
        print("no pairing selected")
        return 1

    status, resp = _http("GET", f"{base}/{pid}", headers=auth)
    if status != 200 or not resp.get("ok"):
        print(f"fetch failed: {resp.get('error', status)}")
        return 1
    p = resp["pairing"]
    if p["status"] != "pending":
        print(f"pairing is {p['status']} — nothing to approve")
        return 1
    print()
    print(f"  Box name:    {p['box_name']}")
    print(f"  Fingerprint: {p['fingerprint']}")
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
        print(f"approve failed: {resp.get('error', status)}")
        return 1
    print(f"approved {pid} — the box can now redeem its token")
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
