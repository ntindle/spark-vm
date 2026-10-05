"""Web Push send-path transport (RFC 8030), stdlib-only — #989.

This is the missing half of the GP1 sender: ``hosted/push_crypto.py``
(proved RFC 8291 ``aes128gcm`` crypto, #967 S1) deliberately has no HTTP
layer; ``hosted/push_payload.py`` (#970) pins the construction discipline.
This module PINs the transport decisions and executes one send attempt.

Decisions (from #989's structural findings):

1. **RFC 8030 POST.** Request line: ``POST <endpoint path>``. Headers:
   ``Authorization: vapid t=<jwt>, k=<pubkey>`` (via
   ``push_crypto.vapid_authorization_header``), ``TTL: <ttl_s>`` (the
   payload's own ttl — a page that outlives the approval is harmful, so
   the push service retains the message exactly as long as the approval
   lives), ``Urgency: high`` (this sender is a page-only channel — D2/D4;
   high is a lock-screen buzz the owner asked for; if a digest channel
   ever appears it gets its own urgency policy), ``Content-Type:
   application/octet-stream``, ``Content-Encoding: aes128gcm``, body =
   ``push_crypto.encrypt_push_message`` output. No ``Topic`` header:
   ``Topic`` replaces pending messages with the same topic, and we never
   want a page to silently replace another.
2. **HTTP client.** ``http.client.HTTPSConnection`` with
   ``ssl.create_default_context()`` (hostname check + cert verification
   on — a self-signed or mismatched push service is a hard failure, not
   a warning). Connect timeout 5 s, per-recv read timeout 10 s — a push
   service is fast; slower than this is a dead peer, not a slow one.
   The response-header phase additionally carries a **total 30 s
   deadline** from request start (``RESPONSE_DEADLINE_S``, #1039): the
   per-recv timeout alone cannot stop a peer that drips bytes inside
   the window, so the deadline re-arms the socket timeout from the
   remaining budget on every read and raises ``socket.timeout``
   (transport-error class → ``retry``) at expiry.
3. **Redirects are never followed.** Any 3xx classifies ``dead-letter``.
   Following a redirect on a VAPID-signed request is a
   credential-orientation question; the answer is no. (``http.client``
   never follows redirects automatically, so this is belt-and-suspenders
   by construction.)
4. **Result taxonomy.** The module classifies every attempt:

   ============  =====================================================
   status        outcome
   ============  =====================================================
   any 2xx       ``accepted`` — record it (feeds #428's §4 retirement).
                 201 is the RFC 8030 norm, but FCM (the likeliest push
                 service for the owner's phone) returns 200 on success;
                 a successful page must never classify dead-letter.
   429           ``retry`` — ``Retry-After`` honored (clamped ≤ 600 s),
                 else the backoff schedule
   410 / 404     ``tombstone`` — subscription is dead; the caller
                 deletes/tombstones it and the dashboard offers
                 re-subscribe
   5xx           ``retry`` — backoff schedule
   400 / 401 / 413 or any other 4xx / any 3xx
                 ``dead-letter`` — our requests are deterministic, so a
                 client error cannot be retried into success; the caller
                 raises the operator-visible alert
   transport error (timeout, DNS, connection refused, TLS failure,
   malformed response)
                 ``retry`` — the push service may come back
   ============  =====================================================

   ``dead-letter`` and ``tombstone`` never retry; ``retry`` never
   sleeps — the module returns a ``retry_after_s`` hint and the caller
   (the #990 enqueue machinery) owns the wait.
5. **VAPID policy.** ``exp`` = now + 12 h (RFC 8292 asks ≤ 24 h);
   ``aud`` = the endpoint origin (scheme + host), derived per send
   because subscriptions live on different push services; ``k`` = the
   VAPID public key passed to the call — rotation swaps the key the
   *caller* holds (lifecycle owned by #988), this module never caches
   keys. ``sub`` is operator configuration, passed per call — there is
   no default subject.
6. **record_size = 1024.** RFC 8291 §4 requires ``rs > len(plaintext) +
   17``. The #970 payload is ≤ 256 B summary + JSON overhead (~120 B),
   so 1024 is comfortable headroom and deliberate — not the 4096
   inherited default. Oversized plaintext is rejected with
   ``ValueError`` *before* any network touch, never silently truncated.
7. **Salt discipline.** This module has no salt parameter anywhere —
   ``encrypt_push_message`` is called with ``salt=None`` so ``secrets``
   mints a fresh one per send. Rule, not convention.
8. **Latency.** The module measures ``latency_ms`` per attempt and
   reports it; it never blocks on sleeps. Real RTT to push services is
   unknown — this measurement is the load-bearing input to the
   inline-vs-outbox decision (#990), not a verdict on it.

#428 §4 retirement mapping: when the outcome is ``accepted``, the
*caller* records ``acceptance_fields(result, ...)`` into the
send-result/acceptance store (#988 owns the D1 table). #428's §4
criterion flips when that store holds a plane-recorded ``accepted``
(any 2xx) for the tenant's subscription. The endpoint, ``p256dh`` and
``auth`` secrets never appear in the record — only the caller's opaque
``subscription_ref``.

Subscription shape (a mapping, keys ``endpoint`` / ``p256dh`` /
``auth`` — the Web Push subscription encoding, base64url strings):

- ``endpoint``: ``https://`` only (cleartext is refused — a VAPID-signed
  request never travels unencrypted), no userinfo (credential-orientation
  fail-closed), non-empty host.
- ``p256dh``: base64url, decodes to exactly 65 octets (uncompressed
  P-256 point), curve-validated per RFC 8291 §7.
- ``auth``: base64url, decodes to exactly 16 octets.

All validation failures are ``ValueError`` raised before any network
touch. The module logs nothing — it is side-effect free; the caller
logs with its own correlation ids (the endpoint never appears in logs).
"""

from __future__ import annotations

import base64
import http.client
import socket
import ssl
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from types import MappingProxyType
from urllib.parse import urlsplit

from . import push_crypto

# ---------------------------------------------------------------------------
# Pinned policies (#989 findings 1–7)
# ---------------------------------------------------------------------------

#: Record size pinned deliberately (finding 5): comfortably above the
#: #970 payload worst case (~380 B + 17 B delimiter/tag), far below the
#: inherited 4096 default.
RECORD_SIZE = 1024

#: VAPID ``exp`` = now + 12 h (finding 4): RFC 8292 asks ≤ 24 h.
VAPID_EXPIRY_S = 12 * 3600

#: Connect/read timeouts (finding 2): a push service is fast; slower is
#: a dead peer.
CONNECT_TIMEOUT_S = 5.0
READ_TIMEOUT_S = 10.0

#: Total deadline for the response-header phase (finding #1039): the
#: per-recv ``READ_TIMEOUT_S`` keeps the fast path, but a push service
#: dripping bytes inside the per-recv window would hold the send path
#: indefinitely. Wall-clock from request start; expiry raises
#: ``socket.timeout`` from the socket's own read path, so it classifies
#: ``retry`` (transport-error class) like every other transport error.
RESPONSE_DEADLINE_S = 30.0

#: Retry bound (finding 3): the module never sleeps and never loops;
#: the #990 caller enforces this many total attempts using
#: ``backoff_s`` / ``parse_retry_after``. Named here (not in the caller)
#: so the policy lives with the taxonomy it bounds.
MAX_ATTEMPTS = 5

#: ``Retry-After`` is honored but clamped — a push service asking us to
#: wait longer than this is telling us the page is already dead.
RETRY_AFTER_MAX_S = 600.0

#: TTL header ceiling (finding 1): approval TTLs live in [60, 3600];
#: the header must stay a sane push-service retention.
TTL_HEADER_MAX_S = 86400

#: Urgency pinned high (finding 1): this sender is a page-only channel.
URGENCY = "high"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

#: Valid ``PushResult.outcome`` values (the taxonomy, finding 3).
OUTCOMES = ("accepted", "retry", "tombstone", "dead-letter")


@dataclass(frozen=True)
class PushResult:
    """The classification of one send attempt (finding 3)."""

    #: One of ``OUTCOMES``.
    outcome: str
    #: HTTP status, or ``None`` when the attempt never got a response
    #: (transport error).
    http_status: int | None
    #: Seconds the caller should wait before the next attempt; set only
    #: for ``retry``. ``None`` for terminal outcomes. The module never
    #: sleeps — the caller (#990) owns the wait.
    retry_after_s: float | None
    #: Wall-clock time for the attempt (network only), milliseconds.
    #: The timer starts after crypto + VAPID signing, so VAPID-sign
    #: timing is excluded from the observable output.
    latency_ms: float
    #: Human-readable classification reason. Never contains the endpoint
    #: or any secret.
    note: str


def backoff_s(attempt: int) -> float:
    """Backoff schedule for ``retry`` outcomes without a usable
    ``Retry-After`` (finding 3): 2 s × 4^(attempt-1), capped at 300 s.
    ``attempt`` is 1-based (the attempt that just failed)."""
    if attempt < 1:
        raise ValueError("attempt is 1-based")
    if attempt >= 5:
        return 300.0  # 2×4^4 already exceeds the cap; no OverflowError
    return min(2.0 * (4.0 ** (attempt - 1)), 300.0)


def parse_retry_after(value: str | None, *, now: float | None = None) -> float | None:
    """Parse an RFC 7231 ``Retry-After`` value (finding 3): delta-seconds
    or an HTTP-date. Returns seconds clamped to ``[0, RETRY_AFTER_MAX_S]``,
    or ``None`` when the value is absent or unparseable (caller falls back
    to ``backoff_s``)."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        delta = float(value)
    except ValueError:
        delta = None
    else:
        if delta != delta or delta == float("inf"):  # NaN / inf
            return None
    if delta is None:
        try:
            when = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        base = time.time() if now is None else now
        delta = when.timestamp() - base
    return max(0.0, min(delta, RETRY_AFTER_MAX_S))


# ---------------------------------------------------------------------------
# Validation (fail-closed, before any network touch)
# ---------------------------------------------------------------------------


def _b64url_decode(value: str, what: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{what} must be a non-empty base64url string")
    padded = value + "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise ValueError(f"{what} is not valid base64url") from exc


def _validated_endpoint(endpoint: object) -> tuple[str, str, int, str]:
    """Return (origin, host, port, path) for a subscription endpoint,
    fail-closed (finding: credential-orientation)."""
    if not isinstance(endpoint, str) or not endpoint:
        raise ValueError("endpoint must be a non-empty string")
    # Fail fast, before any crypto: control characters and non-ASCII
    # would otherwise surface as http.client errors after the ECDH work.
    if any(ord(c) < 32 or ord(c) == 127 for c in endpoint):
        raise ValueError("endpoint must not contain control characters")
    try:
        endpoint.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError("endpoint must be ASCII") from exc
    parts = urlsplit(endpoint)
    if parts.scheme != "https":
        raise ValueError("endpoint must use https (cleartext refused)")
    if parts.username is not None or parts.password is not None:
        raise ValueError("endpoint must not carry userinfo")
    if not parts.hostname:
        raise ValueError("endpoint must have a host")
    host = parts.hostname
    port = parts.port or 443
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query
    # Origin per WHATWG serialization: default port dropped, IPv6
    # literals bracketed (so VAPID aud is well-formed for them too).
    display_host = f"[{host}]" if ":" in host else host
    origin = f"https://{display_host}" + ("" if port == 443 else f":{port}")
    return origin, host, port, path


def _validated_subscription(subscription: object) -> tuple[str, bytes, bytes]:
    """Return (endpoint, p256dh_bytes, auth_bytes)."""
    if not isinstance(subscription, dict) and not hasattr(subscription, "keys"):
        raise ValueError("subscription must be a mapping")
    try:
        endpoint = subscription["endpoint"]
        p256dh = subscription["p256dh"]
        auth = subscription["auth"]
    except (KeyError, TypeError) as exc:
        raise ValueError("subscription needs endpoint/p256dh/auth") from exc
    _validated_endpoint(endpoint)  # fail-closed here too
    ua_public_key = _b64url_decode(p256dh, "p256dh")
    if len(ua_public_key) != 65:
        raise ValueError("p256dh must decode to 65 octets (uncompressed P-256)")
    # RFC 8291 §7 curve check via push_crypto's PUBLIC validator —
    # push_sender never reaches into push_crypto's underscore helpers.
    push_crypto.validate_peer_public_key(ua_public_key)
    auth_secret = _b64url_decode(auth, "auth")
    if len(auth_secret) != 16:
        raise ValueError("auth must decode to 16 octets")
    return endpoint, ua_public_key, auth_secret


def _validated_vapid_keys(private_key: bytes, public_key: bytes) -> None:
    # Shape checks stay subscription-shaped here (subscription-specific
    # messages); the crypto checks ride push_crypto's PUBLIC validators —
    # push_sender never reaches into push_crypto's underscore helpers.
    if not isinstance(private_key, bytes) or len(private_key) != 32:
        raise ValueError("vapid_private_key must be 32 octets")
    push_crypto.validate_private_key(private_key)
    if not isinstance(public_key, bytes) or len(public_key) != 65:
        raise ValueError("vapid_public_key must be 65 octets (uncompressed P-256)")
    push_crypto.validate_peer_public_key(public_key)


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------


class _DeadlineSocketIO(socket.SocketIO):
    """A raw socket file object that re-arms the socket timeout from the
    remaining deadline budget before every read (finding #1039).

    ``http.client`` performs the response-header read through
    ``sock.makefile()``, whose read path funnels into this object's
    ``readinto`` — overriding it here bounds the whole header phase on
    any socket type, without reaching into the socket's own attributes
    (plain ``socket.socket`` forbids instance-attribute shadowing, so a
    recv-patching approach would only work on SSLSocket by accident).
    """

    def __init__(self, sock, mode, deadline):
        super().__init__(sock, mode)
        self._deadline = deadline

    def readinto(self, b):
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise socket.timeout("push response-header deadline exceeded")
        # The per-recv READ_TIMEOUT_S still applies while the budget is
        # ample; the bound tightens as the deadline approaches, and at
        # expiry the read raises instead of waiting.
        self._sock.settimeout(min(READ_TIMEOUT_S, remaining))
        return super().readinto(b)


class _DeadlineSocket:
    """Proxy over the connection socket that bounds the response-header
    read with a total deadline (finding #1039).

    ``http.client`` builds its response reader from ``sock.makefile()``;
    this proxy's ``makefile`` returns a :class:`_DeadlineSocketIO`, so
    the header phase cannot outlive the deadline no matter how slowly
    the peer drips. Every other attribute delegates to the real socket.
    """

    def __init__(self, sock, deadline):
        object.__setattr__(self, "_real_sock", sock)
        object.__setattr__(self, "_deadline", deadline)

    def makefile(self, mode="r", *args, **kwargs):
        return _DeadlineSocketIO(self._real_sock, mode, self._deadline)

    def __getattr__(self, name):
        return getattr(self._real_sock, name)


def _default_transport(*, host: str, port: int, path: str,
                       headers: dict, body: bytes) -> tuple[int, dict, bytes]:
    """The production transport (finding 2): TLS with hostname + cert
    verification, fixed timeouts. ``http.client`` never follows redirects,
    so the no-follow policy holds by construction. Returns
    ``(status, headers, body)``."""
    context = ssl.create_default_context()
    # Explicit: the defaults are the policy, but the policy must not
    # silently change under us if stdlib defaults ever move.
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    conn = http.client.HTTPSConnection(
        host, port, timeout=CONNECT_TIMEOUT_S, context=context)
    try:
        # Finding #1039: the total deadline runs from request start — a
        # per-recv timeout alone cannot stop a slow drip.
        deadline = time.monotonic() + RESPONSE_DEADLINE_S
        conn.request("POST", path, body=body, headers=headers)
        # Bound the response-header read. The timeout is per-recv, not a
        # total deadline; push responses are tiny headers, so this is
        # the right granularity here.
        conn.sock.settimeout(READ_TIMEOUT_S)
        # Swap in the deadline proxy for the header phase only; the real
        # socket is restored before close so teardown stays ordinary.
        real_sock, conn.sock = conn.sock, _DeadlineSocket(conn.sock, deadline)
        try:
            resp = conn.getresponse()
        finally:
            conn.sock = real_sock
        status = resp.status
        resp_headers = {k.lower(): v for k, v in resp.getheaders()}
    finally:
        conn.close()
    # The response body is intentionally NOT read: the caller discards it
    # (a push receipt carries nothing we need), the socket closes anyway,
    # and an unbounded read() is a memory-exhaustion vector against a
    # hostile endpoint (each drip within the per-recv timeout would keep
    # read() looping forever).
    return status, resp_headers, b""


def send_push(*, subscription, plaintext: bytes,
              vapid_private_key: bytes, vapid_public_key: bytes,
              vapid_subject: str, ttl_s: int, attempt: int = 1,
              now: float | None = None, transport=None) -> PushResult:
    """Execute ONE send attempt against the subscription's push service.

    ``subscription`` is a mapping with ``endpoint`` / ``p256dh`` /
    ``auth`` (base64url strings). ``plaintext`` is the serialized #970
    payload. ``ttl_s`` becomes the ``TTL`` header verbatim (finding 1).

    ``attempt`` is 1-based and only feeds ``backoff_s`` when the attempt
    fails without a usable ``Retry-After`` — the module performs exactly
    one attempt per call and never sleeps. ``transport`` defaults to the
    real TLS transport; tests inject the stub transport (documented
    difference: the stub speaks plain HTTP on localhost — the TLS half
    is covered by the default-transport test instead).
    """
    if not isinstance(plaintext, (bytes, bytearray)) or not plaintext:
        raise ValueError("plaintext must be non-empty bytes")
    if len(plaintext) + 17 >= RECORD_SIZE:
        # Finding 5: enforced pre-send, never silently truncated.
        raise ValueError(
            f"plaintext ({len(plaintext)} B) exceeds the pinned record_size "
            f"{RECORD_SIZE} (RFC 8291 §4: rs > len(plaintext)+17)")
    if type(ttl_s) is not int or not 0 < ttl_s <= TTL_HEADER_MAX_S:
        raise ValueError(f"ttl_s must be an int in (0, {TTL_HEADER_MAX_S}]")
    if not isinstance(vapid_subject, str) or not vapid_subject:
        raise ValueError("vapid_subject is operator configuration (no default)")
    if attempt < 1:
        raise ValueError("attempt is 1-based")

    endpoint, ua_public_key, auth_secret = _validated_subscription(subscription)
    _validated_vapid_keys(vapid_private_key, vapid_public_key)
    origin, host, port, path = _validated_endpoint(endpoint)

    moment = time.time() if now is None else now
    # Finding 7: no salt parameter exists on this call — secrets mints a
    # fresh one per send inside encrypt_push_message.
    body = push_crypto.encrypt_push_message(
        plaintext=bytes(plaintext),
        ua_public_key=ua_public_key,
        auth_secret=auth_secret,
        record_size=RECORD_SIZE)
    authz = push_crypto.vapid_authorization_header(
        vapid_private_key=vapid_private_key,
        vapid_public_key=vapid_public_key,
        audience=origin,
        expires_at=int(moment) + VAPID_EXPIRY_S,
        subject=vapid_subject)
    headers = {
        "Authorization": authz,
        "TTL": str(ttl_s),
        "Urgency": URGENCY,
        "Content-Type": "application/octet-stream",
        "Content-Encoding": "aes128gcm",
        "Content-Length": str(len(body)),
    }

    send = _default_transport if transport is None else transport
    started = time.perf_counter()
    try:
        status, resp_headers, _resp_body = send(
            host=host, port=port, path=path, headers=headers, body=body)
    except (socket.timeout, TimeoutError, ConnectionError, ssl.SSLError,
            socket.gaierror, http.client.HTTPException, OSError) as exc:
        # Finding 3: transport errors retry — the push service may come back.
        latency_ms = (time.perf_counter() - started) * 1000.0
        return PushResult(
            outcome="retry", http_status=None,
            retry_after_s=backoff_s(attempt), latency_ms=latency_ms,
            note=f"transport error ({type(exc).__name__}); backoff")
    latency_ms = (time.perf_counter() - started) * 1000.0

    if 200 <= status <= 299:
        # FCM (the likeliest push service for the owner's phone) answers
        # successful Web Push sends with 200, not 201 — any 2xx is an
        # accepted page, and misclassifying a success as dead-letter would
        # break #428's §4 retirement.
        return PushResult(
            outcome="accepted", http_status=status, retry_after_s=None,
            latency_ms=latency_ms, note=f"push service accepted ({status})")
    if status == 429:
        header = resp_headers.get("retry-after")
        parsed = parse_retry_after(header, now=moment) if header else None
        wait = parsed if parsed is not None else backoff_s(attempt)
        return PushResult(
            outcome="retry", http_status=429, retry_after_s=wait,
            latency_ms=latency_ms,
            note="429; Retry-After honored" if parsed is not None
            else "429; backoff schedule")
    if status in (410, 404):
        return PushResult(
            outcome="tombstone", http_status=status, retry_after_s=None,
            latency_ms=latency_ms,
            note=f"subscription dead ({status}); caller tombstones")
    if 500 <= status <= 599:
        return PushResult(
            outcome="retry", http_status=status,
            retry_after_s=backoff_s(attempt), latency_ms=latency_ms,
            note=f"{status}; backoff schedule")
    # Finding 3: any 3xx (redirect — never followed) or any other 4xx is
    # dead-letter. Our requests are deterministic, so a client error
    # cannot be retried into success.
    return PushResult(
        outcome="dead-letter", http_status=status, retry_after_s=None,
        latency_ms=latency_ms,
        note=f"{status}; operator-visible alert, no retry")


# ---------------------------------------------------------------------------
# #428 §4 retirement mapping
# ---------------------------------------------------------------------------


def acceptance_fields(result: PushResult, *, subscription_ref: str,
                      sent_at: float) -> MappingProxyType:
    """The logical acceptance record the caller persists for an
    ``accepted`` result (finding: #428 §4 mapping).

    ``subscription_ref`` is the caller's opaque subscription identity
    (e.g. the (owner_principal, box_id, device) key) — the endpoint,
    ``p256dh`` and ``auth`` secrets never appear here. #988 owns the D1
    table; this pins the *fields*. #428's §4 criterion flips when the
    store holds a plane-recorded record with ``outcome == "accepted"``.

    ``sent_at`` is epoch seconds (float), matching the ``now`` clock the
    caller passes to ``send_push``.
    """
    if result.outcome != "accepted":
        raise ValueError("acceptance records are only built for accepted sends")
    if not isinstance(subscription_ref, str) or not subscription_ref:
        raise ValueError("subscription_ref must be a non-empty string")
    return MappingProxyType({
        "subscription_ref": subscription_ref,
        "outcome": "accepted",
        "http_status": result.http_status,
        "sent_at": sent_at,
        "latency_ms": result.latency_ms,
    })
