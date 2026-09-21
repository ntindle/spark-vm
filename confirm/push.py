#!/usr/bin/env python3
"""push — VAPID Web Push sender for confirmd approvals (GitHub #2 / H2).

A portable component: the operator runs it wherever the deployment lives
(self-hosted box or hosted service) — it is not a hosted-only service.
The VAPID keypair is operator-generated during setup; no real secrets
ever live in the repo.

Protocol: RFC 8030 (Web Push) + RFC 8292 (VAPID) + RFC 8291 (aes128gcm
message encryption).

Flow:
  1. Operator: ``python3 push.py --gen-keys /home/swapd/confirmd/vapid.json``
     (writes {"private","public"} base64url, mode 0600, owned by swapd).
  2. Human opens the confirmd page and taps "Enable notifications": the
     browser's PushManager subscribes with the VAPID public key, and the
     subscription (endpoint + p256dh + auth) is POSTed to
     /api/push/subscribe (owner-authenticated, same as the page).
  3. When swapd files an approval, ``_file_approval`` calls
     ``PushQueue.default().enqueue(item)`` on a daemon thread — one
     locked append to the durable queue journal (``$CONFIRM_DIR/
     push-queue.jsonl``), never on the hot path. The standalone push
     worker (``python3 push.py --worker``, shipped as
     ``push-worker.service``) delivers queued approvals with
     exponential-backoff retry (H14). Fail-open throughout: a queue or
     worker failure never loses the filed approval.
  4. The service worker (/sw.js) shows the notification; tapping it opens
     /approval/<id>.

Payload carries only the approval summary (the same text the page
already shows) plus the approval id — never secrets, never model-authored
free text (finding 49). The queue journal and dead-letter file carry the
same payload shape. Push is disabled unless CONFIRM_VAPID_KEYS names
a readable keypair file AND the `cryptography` package is importable.

Config (env):
  CONFIRM_VAPID_KEYS  path to the keypair JSON (default
                      /home/swapd/confirmd/vapid.json)
  CONFIRM_PUSH_SUBS   path to the subscription store (default
                      $CONFIRM_DIR/push-subscriptions.json, else
                      /home/swapd/approvals/push-subscriptions.json)
  CONFIRM_VAPID_SUB   VAPID subject contact, e.g. mailto:owner@example.com
                      (default mailto:confirmd@localhost)
"""

import base64
import binascii
import contextlib
import fcntl
import json
import logging
import os
import re
import struct
import sys
import time
import urllib.parse
import urllib.request

log = logging.getLogger("sparkvm.push")

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import (
        decode_dss_signature,
    )
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    _CRYPTO_OK = True
except ImportError:
    _CRYPTO_OK = False


# --------------------------------------------------------------------------
# base64url helpers
# --------------------------------------------------------------------------

def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(s: str) -> bytes:
    if not isinstance(s, str):
        raise ValueError("not a string")
    s = s.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]*", s):
        raise ValueError("not base64url")
    pad = "=" * (-len(s) % 4)
    try:
        return base64.urlsafe_b64decode(s + pad)
    except (binascii.Error, ValueError):
        raise ValueError("not base64url")


# --------------------------------------------------------------------------
# VAPID keypair
# --------------------------------------------------------------------------

def _need_crypto():
    if not _CRYPTO_OK:
        raise RuntimeError(
            "push: the `cryptography` package is required "
            "(pip install cryptography)")


def gen_keypair():
    """Generate an ES256 (P-256) VAPID keypair.

    Returns (private_b64u, public_b64u): 32-byte private scalar and the
    65-byte uncompressed public point, both base64url.
    """
    _need_crypto()
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PublicFormat)
    priv = ec.generate_private_key(ec.SECP256R1())
    priv_raw = priv.private_numbers().private_value.to_bytes(32, "big")
    pub_raw = priv.public_key().public_bytes(
        Encoding.X962, PublicFormat.UncompressedPoint)
    return b64url_encode(priv_raw), b64url_encode(pub_raw)


def vapid_jwt(audience: str, private_b64u: str, subject: str,
              ttl_seconds: int = 12 * 3600) -> str:
    """Build a VAPID JWT (RFC 8292 §2): ES256-signed, exp ≤ 24h."""
    _need_crypto()
    # RFC 8292 §2: exp MUST NOT exceed 24h from now.
    ttl_seconds = max(60, min(ttl_seconds, 24 * 3600))
    priv_raw = b64url_decode(private_b64u)
    if len(priv_raw) != 32:
        raise ValueError("VAPID private key must decode to 32 bytes")
    priv = ec.derive_private_key(int.from_bytes(priv_raw, "big"),
                                 ec.SECP256R1())
    now = int(time.time())
    header = b64url_encode(json.dumps(
        {"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
    claims = b64url_encode(json.dumps(
        {"aud": audience, "exp": now + ttl_seconds, "sub": subject},
        separators=(",", ":")).encode())
    signing_input = (header + "." + claims).encode()
    der = priv.sign(signing_input, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    raw = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return (signing_input + b"." + b64url_encode(raw).encode()).decode()


# --------------------------------------------------------------------------
# RFC 8291 aes128gcm message encryption
# --------------------------------------------------------------------------

def encrypt_message(receiver_pub_b64u: str, auth_secret_b64u: str,
                    plaintext: bytes) -> bytes:
    """Encrypt a push payload for one subscription (RFC 8291, aes128gcm).

    Returns the request body: salt(16) || rs(4) || idlen(1) ||
    ephemeral-pub(65) || ciphertext.
    """
    _need_crypto()
    receiver_pub_raw = b64url_decode(receiver_pub_b64u)
    auth_secret = b64url_decode(auth_secret_b64u)
    if len(receiver_pub_raw) != 65 or receiver_pub_raw[0] != 0x04:
        raise ValueError("p256dh must be a 65-byte uncompressed point")
    if len(auth_secret) != 16:
        raise ValueError("auth secret must be 16 bytes")
    receiver_pub = ec.EllipticCurvePublicNumbers(
        int.from_bytes(receiver_pub_raw[1:33], "big"),
        int.from_bytes(receiver_pub_raw[33:65], "big"),
        ec.SECP256R1(),
    ).public_key()
    eph_priv = ec.generate_private_key(ec.SECP256R1())
    shared = eph_priv.exchange(ec.ECDH(), receiver_pub)
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PublicFormat)
    eph_pub_raw = eph_priv.public_key().public_bytes(
        Encoding.X962, PublicFormat.UncompressedPoint)
    info = b"WebPush: info\x00" + receiver_pub_raw + eph_pub_raw
    prk = HKDF(algorithm=hashes.SHA256(), length=32,
               salt=auth_secret, info=info).derive(shared)
    salt = os.urandom(16)
    cek = HKDF(algorithm=hashes.SHA256(), length=16, salt=salt,
               info=b"Content-Encoding: aes128gcm\x00").derive(prk)
    nonce = HKDF(algorithm=hashes.SHA256(), length=12, salt=salt,
                info=b"Content-Encoding: nonce\x00").derive(prk)
    # Single record: plaintext || 0x02 (last-record delimiter, RFC 8291
    # §3). In single-record mode the delimiter is simply the final octet,
    # so stripping is unambiguous.
    ct = AESGCM(cek).encrypt(nonce, plaintext + b"\x02", b"")
    rs = 4096
    return (salt + struct.pack(">L", rs) + bytes([len(eph_pub_raw)])
            + eph_pub_raw + ct)


# --------------------------------------------------------------------------
# Subscription store (atomic JSON, owner-readable only)
# --------------------------------------------------------------------------

_SUBS_VERSION = 1
_NOTIFIED_CAP = 1000


def _atomic_write_json(path: str, obj) -> None:
    # Engineering review: create the tmp file 0600 from the start — the
    # old write-then-chmod left a world-readable window for endpoint
    # URLs (capability-ish tokens).
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    os.replace(tmp, path)


@contextlib.contextmanager
def _locked(path: str):
    """Exclusive cross-process lock for load-modify-save on `path`.

    QA review: SubscriptionStore and NotifiedLog are written from two
    different processes (confirmd's ThreadingHTTPServer and mitmproxy's
    swap_addon) plus concurrent threads inside each. Atomic os.replace
    alone does not prevent a stale read-modify-write from silently
    dropping a subscription. The lock is a `<path>.lock` sidecar.
    """
    lock_path = path + ".lock"
    with open(lock_path, "a+b") as lf:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


class SubscriptionStore:
    """push-subscriptions.json: [{endpoint, keys:{p256dh,auth}, created}]."""

    def __init__(self, path: str):
        self.path = path

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                doc = json.load(f)
            subs = doc.get("subscriptions")
            if isinstance(subs, list):
                return [s for s in subs if isinstance(s, dict)]
        except (OSError, ValueError):
            pass
        return []

    def _save(self, subs):
        _atomic_write_json(self.path, {"version": _SUBS_VERSION,
                                       "subscriptions": subs})

    @staticmethod
    def validate(endpoint: str, p256dh: str, auth: str) -> None:
        """Raise ValueError on anything that is not a well-formed sub."""
        try:
            parts = urllib.parse.urlparse(endpoint)
        except ValueError:
            raise ValueError("bad endpoint URL")
        if parts.scheme != "https" or not parts.netloc or len(endpoint) > 2048:
            raise ValueError("endpoint must be an https URL")
        pub = b64url_decode(p256dh)
        if len(pub) != 65 or pub[0] != 0x04:
            raise ValueError("p256dh must be a 65-byte uncompressed point")
        if len(b64url_decode(auth)) != 16:
            raise ValueError("auth must decode to 16 bytes")

    def add(self, endpoint: str, p256dh: str, auth: str) -> None:
        self.validate(endpoint, p256dh, auth)
        with _locked(self.path):
            subs = [s for s in self._load() if s.get("endpoint") != endpoint]
            subs.append({"endpoint": endpoint,
                         "keys": {"p256dh": p256dh, "auth": auth},
                         "created": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                  time.gmtime())})
            self._save(subs)

    def remove(self, endpoint: str) -> bool:
        with _locked(self.path):
            subs = self._load()
            kept = [s for s in subs if s.get("endpoint") != endpoint]
            if len(kept) != len(subs):
                self._save(kept)
                return True
            return False

    def all(self):
        return self._load()


# --------------------------------------------------------------------------
# Notified log: which approval ids already pushed (idempotency)
# --------------------------------------------------------------------------

class NotifiedLog:
    def __init__(self, path: str):
        self.path = path

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                doc = json.load(f)
            noted = doc.get("notified")
            if isinstance(noted, dict):
                return noted
        except (OSError, ValueError):
            pass
        return {}

    def seen(self, aid: str) -> bool:
        return aid in self._load()

    def mark(self, aid: str) -> None:
        with _locked(self.path):
            noted = self._load()
            noted[aid] = int(time.time())
            if len(noted) > _NOTIFIED_CAP:
                # Drop the oldest entries.
                for old in sorted(noted, key=noted.get)[:len(noted) - _NOTIFIED_CAP]:
                    del noted[old]
            _atomic_write_json(self.path, {"notified": noted})


# --------------------------------------------------------------------------
# Sender
# --------------------------------------------------------------------------

AID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_SEND_TIMEOUT = 15


def _default_keys_path() -> str:
    return os.environ.get("CONFIRM_VAPID_KEYS",
                          "/home/swapd/confirmd/vapid.json")


def _default_subs_path() -> str:
    if "CONFIRM_PUSH_SUBS" in os.environ:
        return os.environ["CONFIRM_PUSH_SUBS"]
    d = os.environ.get("CONFIRM_DIR", "/home/swapd/approvals")
    return os.path.join(d, "push-subscriptions.json")


def _default_notified_path() -> str:
    return _default_subs_path() + ".notified.json"


class PushSender:
    def __init__(self, keys_path: str, subs_path: str, subject: str):
        self.keys_path = keys_path
        self.subs = SubscriptionStore(subs_path)
        self.notified = NotifiedLog(subs_path + ".notified.json")
        self.subject = subject
        self._private = None
        self._public = None
        # Product review: surface WHY push is disabled, not just that it
        # is. None when enabled.
        self.disabled_reason = None
        self._load_keys()

    @classmethod
    def default(cls):
        return cls(_default_keys_path(), _default_subs_path(),
                   os.environ.get("CONFIRM_VAPID_SUB",
                                  "mailto:confirmd@localhost"))

    def _load_keys(self):
        if not _CRYPTO_OK:
            self.disabled_reason = ("no-cryptography: pip/apt install the "
                                    "`cryptography` package")
            log.warning("push: disabled (%s)", self.disabled_reason)
            return
        try:
            with open(self.keys_path, encoding="utf-8") as f:
                doc = json.load(f)
            priv = b64url_decode(doc["private"])
            pub = b64url_decode(doc["public"])
            if len(priv) != 32 or len(pub) != 65 or pub[0] != 0x04:
                raise ValueError("bad key lengths")
            self._private = doc["private"]
            self._public = doc["public"]
            # Issue #77 (L2): a group/world-readable private key file was
            # silently accepted. Warn loudly; the fix is `chmod 600`.
            mode = os.stat(self.keys_path).st_mode & 0o777
            if mode & 0o077:
                log.warning("push: vapid keys file %s is group/world-readable "
                            "(mode %o); chmod 600 recommended",
                            self.keys_path, mode)
        except (OSError, ValueError, KeyError, TypeError) as e:
            # Engineering review: TypeError covers a keys file holding
            # valid JSON that isn't a dict (e.g. `[]`).
            self.disabled_reason = ("no-keys: %s unreadable or invalid "
                                    "(%s)" % (self.keys_path, e))
            log.warning("push: disabled (%s)", self.disabled_reason)

    @property
    def enabled(self) -> bool:
        return _CRYPTO_OK and self._private is not None

    @property
    def public_key_b64u(self):
        return self._public

    # -- low level ------------------------------------------------------
    def _send_one(self, sub: dict, payload: bytes) -> str:
        """POST one encrypted push. Returns 'ok', 'prune', or 'retry'."""
        endpoint = sub["endpoint"]
        keys = sub.get("keys", {})
        body = encrypt_message(keys["p256dh"], keys["auth"], payload)
        audience = "%s://%s" % urllib.parse.urlparse(endpoint)[:2]
        jwt = vapid_jwt(audience, self._private, self.subject)
        req = urllib.request.Request(
            endpoint, data=body, method="POST",
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Encoding": "aes128gcm",
                # TTL 3600 matches the approval lifetime: confirmd reaps
                # pending approvals after 1h, so a later delivery would
                # tap through to an expired page anyway.
                "TTL": "3600",
                "Authorization": "vapid t=%s, k=%s" % (jwt, self._public),
            })
        try:
            with urllib.request.urlopen(req, timeout=_SEND_TIMEOUT) as resp:
                code = resp.getcode()
        except urllib.error.HTTPError as e:
            code = e.code
        if code in (200, 201, 202):
            return "ok"
        if code in (404, 410):
            return "prune"  # subscription gone at the push service
        log.warning("push: send to %s returned %s",
                    urllib.parse.urlparse(endpoint).netloc, code)
        return "retry"

    # -- public API ------------------------------------------------------
    def notify_approval(self, item: dict) -> int:
        """Push one approval to every stored subscription.

        Fail-open: never raises. Returns the number of successful sends.

        QA/Engineering review: the idempotency mark is written ONLY when
        the attempt had no transient failure (every subscription resolved
        ok or was pruned, or there were no subscriptions). If every send
        raised or returned "retry", the approval is left unmarked — a
        transient outage must not become a silently dropped notification.
        Since H14 the retry path is the push worker (``push.py --worker``);
        a partial failure leaves the approval unmarked AND enqueued so the
        worker retries it — the loud log line below is the operator signal.
        """
        if not self.enabled:
            return 0
        try:
            aid, payload = _build_approval_payload(item)
            if not AID_RE.match(aid):
                log.warning("push: refusing to notify for bad id %r", aid)
                return 0
            if self.notified.seen(aid):
                return 0
            sent, pending = self._send_payload(aid, payload)
            if pending:
                log.error("push: transient failure notifying approval %s "
                          "(%d/%d sent) — NOT marked notified; the push "
                          "worker retries it (push.py --worker)",
                          aid, sent, len(self.subs.all()))
            else:
                self.notified.mark(aid)
            return sent
        except Exception:
            log.exception("push: notify_approval failed")
            return 0

    def _send_payload(self, aid: str, payload: bytes) -> tuple:
        """One delivery round of an already-built payload.

        Returns (sent, pending): sent = subscriptions that accepted;
        pending = True if any subscription hit a transient failure (the
        caller must NOT mark the approval notified; a retry is needed).
        Never raises. Shared by notify_approval and the H14 queue worker.
        """
        sent = 0
        pending = False
        for sub in self.subs.all():
            try:
                res = self._send_one(sub, payload)
            except Exception:
                log.exception("push: send failed")
                pending = True
                continue
            if res == "ok":
                sent += 1
            elif res == "prune":
                self.subs.remove(sub.get("endpoint", ""))
            else:  # "retry": transient — do not mark as notified
                pending = True
        return sent, pending


def _build_approval_payload(item: dict) -> tuple:
    """Build the (aid, payload) wire pair for an approval item.

    Single source of truth for the summary truncation + payload cap,
    shared by notify_approval and the H14 queue worker so the wire bytes
    are identical whichever path delivers them. Never raises for
    dict-shaped items.
    """
    aid = str(item.get("id") or "")
    summary = str(item.get("summary") or "New approval request")
    if len(summary) > 200:
        summary = summary[:197] + "..."
    payload = json.dumps(
        {"title": "Approval needed",
         "body": summary,
         "approval_id": aid},
        separators=(",", ":")).encode()
    if len(payload) > 3800:
        payload = json.dumps(
            {"title": "Approval needed",
             "body": "Open confirmd to review.",
             "approval_id": aid},
            separators=(",", ":")).encode()
    return aid, payload


# --------------------------------------------------------------------------
# H14 (part a): standalone push service — enqueue/retry
# --------------------------------------------------------------------------
#
# Before H14, a transient push failure (dead push service, 5xx, timeout)
# left the approval unmarked but had no retry path — only a loud log line.
# The queue closes that: swapd enqueues every filed approval (fast, one
# locked append, never on the hot path), and the standalone worker
# (`push.py --worker`, or `push-worker.service`) delivers with
# exponential-backoff retry. After QUEUE_MAX_ATTEMPTS failed attempts the
# entry is dead-lettered with a loud log line — the operator signal.
#
# Both halves are portable: they read the same CONFIRM_* env paths as the
# sender, run wherever the deployment lives, and touch no hosted-only
# surface. The payload on the wire is byte-identical to the inline path
# (shared _build_approval_payload); the queue journal and dead-letter
# files carry only approval ids + summaries, never secrets.

def _default_queue_path() -> str:
    if "CONFIRM_PUSH_QUEUE" in os.environ:
        return os.environ["CONFIRM_PUSH_QUEUE"]
    d = os.environ.get("CONFIRM_DIR", "/home/swapd/approvals")
    return os.path.join(d, "push-queue.jsonl")


def _default_dead_path() -> str:
    if "CONFIRM_PUSH_DEAD" in os.environ:
        return os.environ["CONFIRM_PUSH_DEAD"]
    d = os.environ.get("CONFIRM_DIR", "/home/swapd/approvals")
    return os.path.join(d, "push-queue-dead.jsonl")


# Retry schedule: after a failed attempt n (1-based), the entry is due
# again at now + min(CAP, BASE * 2**(n-1)) — 1m, 2m, 4m, 8m, 16m,
# 30m, 30m, then dead-letter. Worst case the worker chases a dead push
# service for ~1.5h before giving up loudly.
QUEUE_MAX_ATTEMPTS = 8
QUEUE_BACKOFF_BASE = 60.0
QUEUE_BACKOFF_CAP = 1800.0
# Claim lease: a worker pass marks due entries "inflight" and bumps
# next_at by this, so a second concurrent pass (or a crashed pass)
# can't double-send — entries become due again only after the lease.
QUEUE_CLAIM_TTL = 300.0


def _queue_next_at(attempts: int, now: float) -> float:
    """Next due time after `attempts` failed attempts (1-based)."""
    delay = min(QUEUE_BACKOFF_CAP, QUEUE_BACKOFF_BASE * (2 ** (attempts - 1)))
    return now + delay


class PushQueue:
    """Durable enqueue/retry queue for push notifications.

    One JSONL journal (`queue_path`), one JSONL dead-letter file
    (`dead_path`), each line one entry::

        {"aid": ..., "summary": ..., "enqueued_at": ..., "attempts": 0,
         "next_at": ..., "state": "pending"}

    Cross-process safety reuses the module's `_locked` sidecar pattern:
    every journal read-modify-write holds the exclusive lock, and entries
    are claimed (state=inflight + next_at bumped by the claim TTL) under
    the lock before any network send happens, so two worker processes
    can't deliver the same approval twice and a crashed worker's claims
    self-heal after the TTL.
    """

    def __init__(self, queue_path: str, dead_path: str, notified_path: str):
        self.queue_path = queue_path
        self.dead_path = dead_path
        self.notified = NotifiedLog(notified_path)

    @classmethod
    def default(cls):
        subs_path = _default_subs_path()
        return cls(_default_queue_path(), _default_dead_path(),
                   subs_path + ".notified.json")

    # -- enqueue ------------------------------------------------------
    def enqueue(self, item: dict) -> str:
        """File an approval for worker delivery.

        Returns "queued" | "duplicate" | "notified" | "invalid".
        Fail-open: never raises — a queue failure must never lose the
        filed approval (the worker simply never learns about it; the
        loud log line is the signal).
        """
        try:
            aid, _payload = _build_approval_payload(item)
            if not AID_RE.match(aid):
                log.warning("push-queue: refusing to enqueue bad id %r",
                            aid)
                return "invalid"
            if self.notified.seen(aid):
                return "notified"
            now = time.time()
            summary = str(item.get("summary") or "New approval request")
            with _locked(self.queue_path):
                if self._aid_present(aid):
                    return "duplicate"
                entry = {"aid": aid, "summary": summary,
                         "enqueued_at": now, "attempts": 0,
                         "next_at": now, "state": "pending"}
                fd = os.open(self.queue_path,
                             os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        f.write(json.dumps(entry, separators=(",", ":"))
                                + "\n")
                        f.flush()
                        os.fsync(f.fileno())
                except BaseException:
                    # fdopen took ownership of fd; on failure the file
                    # object closes it.
                    raise
            log.info("push-queue: enqueued approval %s", aid)
            return "queued"
        except Exception:
            log.exception("push-queue: enqueue failed")
            return "invalid"

    def _read_all(self):
        """All journal entries in file order; corrupt lines are logged
        and skipped, never fatal."""
        entries = []
        try:
            with open(self.queue_path, encoding="utf-8") as f:
                for lineno, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                    except ValueError:
                        log.error("push-queue: skipping corrupt line %d",
                                  lineno)
                        continue
                    if isinstance(e, dict) and e.get("aid"):
                        entries.append(e)
                    else:
                        log.error("push-queue: skipping malformed line %d",
                                  lineno)
        except FileNotFoundError:
            pass
        return entries

    def _rewrite(self, entries):
        """Rewrite the whole journal atomically (0600, fsync)."""
        tmp = self.queue_path + ".tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                for e in entries:
                    f.write(json.dumps(e, separators=(",", ":")) + "\n")
                f.flush()
                os.fsync(f.fileno())
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        os.replace(tmp, self.queue_path)

    def _aid_present(self, aid: str) -> bool:
        return any(e.get("aid") == aid for e in self._read_all())

    # -- worker -------------------------------------------------------
    def run_once(self, sender=None, now=None) -> dict:
        """One delivery pass over due entries. Returns a stats dict.

        Never raises. With a disabled sender (no keys / no crypto) the
        pass is skipped loudly and entries stay queued — they deliver
        once the operator configures keys.
        """
        stats = {"processed": 0, "sent": 0, "rescheduled": 0, "dead": 0,
                 "errors": 0}
        now = time.time() if now is None else now
        if sender is None:
            sender = PushSender.default()
        if not sender.enabled:
            log.warning("push-queue: worker pass skipped — push disabled "
                        "(%s)", sender.disabled_reason)
            stats["disabled"] = True
            return stats
        # Claim due entries under the lock; the sends happen unlocked so
        # a dead push service (15s x N timeouts) can't wedge enqueues.
        # Both "pending" and "inflight" entries are eligible: the claim
        # below bumps next_at by the lease TTL, so a live claim can't be
        # double-claimed, while a crashed worker's claims self-heal once
        # the TTL passes.
        with _locked(self.queue_path):
            entries = self._read_all()
            due = [e for e in entries
                   if e.get("state") in ("pending", "inflight")
                   and e.get("next_at", 0) <= now]
            for e in due:
                e["state"] = "inflight"
                e["next_at"] = now + QUEUE_CLAIM_TTL
            if due:
                self._rewrite(entries)
        for e in due:
            aid = e["aid"]
            stats["processed"] += 1
            try:
                _built_aid, payload = _build_approval_payload(
                    {"id": aid, "summary": e.get("summary", "")})
                _sent, pending = sender._send_payload(aid, payload)
            except Exception:
                log.exception("push-queue: delivery crashed for %s", aid)
                _sent, pending = 0, True
            if pending:
                attempts = int(e.get("attempts", 0)) + 1
                if attempts >= QUEUE_MAX_ATTEMPTS:
                    self._dead_letter(e, attempts, "max-attempts")
                    self._finalize(aid, remove=True)
                    stats["dead"] += 1
                else:
                    self._finalize(
                        aid, attempts=attempts,
                        next_at=_queue_next_at(attempts, now),
                        state="pending")
                    stats["rescheduled"] += 1
                    log.warning("push-queue: attempt %d/%d failed for %s; "
                                "next try in %.0fs",
                                attempts, QUEUE_MAX_ATTEMPTS, aid,
                                _queue_next_at(attempts, now) - now)
            else:
                sender.notified.mark(aid)
                self._finalize(aid, remove=True)
                stats["sent"] += 1
        return stats

    def run_forever(self, interval: float = 30.0):
        """The standalone push service: loop run_once forever."""
        log.info("push-queue: worker started (interval %.0fs, queue %s)",
                 interval, self.queue_path)
        while True:
            try:
                stats = self.run_once()
                if stats.get("processed"):
                    log.info("push-queue: pass done %s", stats)
            except Exception:
                # run_once never raises by contract; this is belt and
                # suspenders so the service can never die silently.
                log.exception("push-queue: worker pass crashed")
            time.sleep(interval)

    def _finalize(self, aid: str, remove: bool = False, attempts: int = 0,
                  next_at: float = 0.0, state: str = "pending"):
        """Apply a delivery outcome to one entry (under the lock)."""
        with _locked(self.queue_path):
            entries = self._read_all()
            kept = []
            for e in entries:
                if e.get("aid") != aid:
                    kept.append(e)
                    continue
                if remove:
                    continue
                e["attempts"] = attempts
                e["next_at"] = next_at
                e["state"] = state
                kept.append(e)
            self._rewrite(kept)

    def _dead_letter(self, entry: dict, attempts: int, reason: str):
        """Move an exhausted entry to the dead-letter file, loudly."""
        record = dict(entry)
        record["dead_at"] = time.time()
        record["dead_reason"] = reason
        record["attempts"] = attempts
        with _locked(self.dead_path):
            fd = os.open(self.dead_path,
                         os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(json.dumps(record, separators=(",", ":"))
                            + "\n")
                    f.flush()
                    os.fsync(f.fileno())
            except BaseException:
                raise
        log.error("push-queue: DEAD-LETTERED approval %s after %d attempts "
                  "(%s) — see %s; re-enqueue by re-filing or clearing the "
                  "notified mark", entry.get("aid"), attempts, reason,
                  self.dead_path)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv):
    import argparse
    ap = argparse.ArgumentParser(
        description="VAPID Web Push sender for confirmd approvals")
    ap.add_argument("--gen-keys", metavar="PATH",
                    help="generate a VAPID keypair JSON at PATH (mode 0600)")
    ap.add_argument("--test-push", action="store_true",
                    help="send a test notification to every stored "
                         "subscription (operator verify step)")
    ap.add_argument("--worker", action="store_true",
                    help="run the H14 standalone push service: loop "
                         "delivering queued approvals with "
                         "exponential-backoff retry (systemd runs this)")
    ap.add_argument("--worker-once", action="store_true",
                    help="one push-worker delivery pass over due queue "
                         "entries, then exit (prints a stats line)")
    ap.add_argument("--worker-interval", type=float, default=30.0,
                    metavar="SECONDS",
                    help="seconds between worker passes (default 30)")
    args = ap.parse_args(argv)
    if args.worker_once:
        stats = PushQueue.default().run_once()
        print("push worker pass: %s" % (stats,))
        return 0
    if args.worker:
        if args.worker_interval <= 0:
            print("error: --worker-interval must be positive", file=sys.stderr)
            return 2
        PushQueue.default().run_forever(args.worker_interval)
        return 0  # pragma: no cover (infinite loop)
    if args.gen_keys:
        _need_crypto()
        priv, pub = gen_keypair()
        path = args.gen_keys
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump({"private": priv, "public": pub,
                           "created": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                    time.gmtime())},
                          f, indent=2)
                f.write("\n")
        except BaseException:
            try:
                os.unlink(path)
            except OSError:
                pass
            raise
        print("wrote %s (mode 0600)" % path)
        print("public key (for /api/push/config): %s" % pub)
        return 0
    if args.test_push:
        # Product review: the operator verify step. Sends a real push
        # through the configured keys to every stored subscription.
        sender = PushSender.default()
        if not sender.enabled:
            print("push disabled: %s" % sender.disabled_reason)
            return 1
        aid = "test-%d" % int(time.time())
        sent = sender.notify_approval(
            {"id": aid,
             "summary": "Test notification from confirmd push "
                        "(safe to ignore)."})
        print("test push %s: %d subscription(s) accepted it"
              % (aid, sent))
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
