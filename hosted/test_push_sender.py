"""Tests for hosted/push_sender.py (#989) against a stub push service.

The stub is a real local HTTP server (stdlib ``http.server``) with a
scripted response queue, reached through an injected plain-HTTP
transport — the production transport speaks TLS. That difference is
documented and compensated: ``test_default_transport_enforces_tls``
pins the production transport's TLS policy (hostname + cert
verification, fixed timeouts) without any network.
"""

import base64
import http.client
import http.server
import inspect
import json
import secrets
import socket
import ssl
import struct
import threading
import time
from collections import deque
from types import MappingProxyType
from unittest import mock

import pytest

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hosted import push_crypto, push_sender


# ---------------------------------------------------------------------------
# Stub push service
# ---------------------------------------------------------------------------


class _StubHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "StubPush/1.0"

    def _handle(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        server = self.server
        server.requests.append({
            "method": self.command,
            "path": self.path,
            "headers": {k.lower(): v for k, v in self.headers.items()},
            "body": body,
        })
        if server.scripted:
            status, headers, resp_body = server.scripted.popleft()
        else:
            status, headers, resp_body = 201, {}, b""
        resp_body = resp_body or b""
        self.send_response(status)
        self.send_header("Content-Length", str(len(resp_body)))
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(resp_body)

    do_POST = _handle

    def log_message(self, *args):
        pass


class StubPushService:
    """A scripted push-service stub. ``scripted`` is a deque of
    (status, headers, body) tuples consumed one per request."""

    def __init__(self):
        self.server = http.server.HTTPServer(("127.0.0.1", 0), _StubHandler)
        self.server.requests = []
        self.server.targets = []  # (host, port, path) per transport call
        self.server.scripted = deque()
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    @property
    def port(self):
        return self.server.server_address[1]

    def script(self, *responses):
        """Queue (status, headers, body) responses."""
        self.server.scripted.extend(responses)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


@pytest.fixture()
def stub():
    with StubPushService() as service:
        yield service


def _subscription(endpoint_host="push.example.com", endpoint_port=None, query=None):
    priv, pub = push_crypto.generate_keypair()
    auth = secrets.token_bytes(16)
    endpoint = f"https://{endpoint_host}"
    if endpoint_port:
        endpoint += f":{endpoint_port}"
    endpoint += "/wp/abc123"
    if query:
        endpoint += "?" + query
    return {
        "endpoint": endpoint,
        "p256dh": _b64url(pub),
        "auth": _b64url(auth),
    }


def _vapid_keys():
    return push_crypto.generate_keypair()


def _stub_transport(stub):
    def transport(*, host, port, path, headers, body):
        # Documented stub difference: plain HTTP to localhost. The
        # production transport speaks TLS; its policy is pinned by
        # test_default_transport_enforces_tls instead. The request
        # target (host/port/path) is recorded so tests pin that
        # send_push computed it from the subscription endpoint.
        stub.server.targets.append((host, port, path))
        conn = http.client.HTTPConnection("127.0.0.1", stub.port, timeout=5)
        try:
            conn.request("POST", path, body=body, headers=headers)
            resp = conn.getresponse()
            return resp.status, {k.lower(): v for k, v in resp.getheaders()}, resp.read()
        finally:
            conn.close()
    return transport


def _send(stub, sub=None, plaintext=b'{"aid":"a1","ttl_s":600,"summary":"hi"}',
          ttl_s=600, attempt=1, now=1_700_000_000.0, transport=None,
          vapid_subject="mailto:ops@example.com",
          vapid_priv=None, vapid_pub=None, **kw):
    sub = sub if sub is not None else _subscription()
    if vapid_priv is None or vapid_pub is None:
        vapid_priv, vapid_pub = _vapid_keys()
    return push_sender.send_push(
        subscription=sub, plaintext=plaintext,
        vapid_private_key=vapid_priv, vapid_public_key=vapid_pub,
        vapid_subject=vapid_subject, ttl_s=ttl_s,
        attempt=attempt, now=now,
        transport=_stub_transport(stub) if transport is None else transport,
        **kw), sub


def _jwt_claims(authorization):
    assert authorization.startswith("vapid t="), authorization
    token = authorization[len("vapid t="):].split(", k=")[0]
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


# ---------------------------------------------------------------------------
# Accepted + request-shape pins
# ---------------------------------------------------------------------------


def test_accepted_201_and_request_shape(stub):
    result, sub = _send(stub)
    assert result.outcome == "accepted"
    assert result.http_status == 201
    assert result.retry_after_s is None
    assert 0 < result.latency_ms < 15_000

    assert len(stub.server.requests) == 1
    req = stub.server.requests[0]
    assert req["method"] == "POST"
    # The request target is computed from the subscription endpoint —
    # the stub records what the transport was asked to hit.
    assert req["path"] == "/wp/abc123"
    assert stub.server.targets == [("push.example.com", 443, "/wp/abc123")]
    h = req["headers"]
    assert h["ttl"] == "600"
    assert h["urgency"] == "high"
    assert "topic" not in h, "Topic must never be set (replacement semantics)"
    assert h["content-type"] == "application/octet-stream"
    assert h["content-encoding"] == "aes128gcm"

    # Body: salt(16) || rs(u32be) || 0x41 || as_public(65) || ciphertext.
    body = req["body"]
    assert len(body) > 86
    assert struct.unpack(">I", body[16:20])[0] == push_sender.RECORD_SIZE == 1024
    assert body[20:21] == b"\x41"
    assert len(body[21:86]) == 65


@pytest.mark.parametrize("status", [200, 201, 202, 204])
def test_accepted_2xx(stub, status):
    # 201 is the RFC 8030 norm, but FCM answers successful Web Push
    # sends with 200 — any 2xx is an accepted page.
    stub.script((status, {}, b""))
    result, _ = _send(stub)
    assert result.outcome == "accepted", status
    assert result.http_status == status
    assert result.retry_after_s is None


def test_vapid_policy_exp_aud_k(stub):
    vapid_priv, vapid_pub = _vapid_keys()
    result, sub = _send(stub, now=1_700_000_000.0,
                        vapid_priv=vapid_priv, vapid_pub=vapid_pub)
    assert result.outcome == "accepted"
    h = stub.server.requests[0]["headers"]
    # Re-derive what the header must carry: aud = endpoint origin.
    claims = _jwt_claims(h["authorization"])
    assert claims["aud"] == "https://push.example.com"
    assert claims["exp"] == 1_700_000_000 + push_sender.VAPID_EXPIRY_S
    assert claims["exp"] - 1_700_000_000 <= 24 * 3600
    assert claims["sub"] == "mailto:ops@example.com"
    k_param = h["authorization"].split(", k=")[1]
    # k= must be EXACTLY the VAPID public key passed to the call
    # (rotation correctness depends on it) — not just a well-formed point.
    assert k_param == _b64url(vapid_pub)


def test_vapid_aud_uses_endpoint_origin_with_port(stub):
    result, sub = _send(stub, sub=_subscription(endpoint_port=8443))
    claims = _jwt_claims(stub.server.requests[0]["headers"]["authorization"])
    assert claims["aud"] == "https://push.example.com:8443"


# ---------------------------------------------------------------------------
# Result taxonomy
# ---------------------------------------------------------------------------


def test_tombstone_410_and_404(stub):
    for status in (410, 404):
        stub.script((status, {}, b""))
        result, _ = _send(stub)
        assert result.outcome == "tombstone", status
        assert result.http_status == status
        assert result.retry_after_s is None


def test_retry_429_with_retry_after(stub):
    stub.script((429, {"Retry-After": "30"}, b""))
    result, _ = _send(stub, attempt=1)
    assert result.outcome == "retry"
    assert result.retry_after_s == 30.0


def test_retry_429_without_retry_after_uses_backoff(stub):
    stub.script((429, {}, b""))
    result, _ = _send(stub, attempt=2)
    assert result.outcome == "retry"
    assert result.retry_after_s == push_sender.backoff_s(2) == 8.0


def test_retry_429_retry_after_http_date(stub):
    future = time.strftime("%a, %d %b %Y %H:%M:%S GMT",
                           time.gmtime(1_700_000_000 + 90))
    stub.script((429, {"Retry-After": future}, b""))
    result, _ = _send(stub, now=1_700_000_000.0)
    assert result.outcome == "retry"
    assert 85.0 <= result.retry_after_s <= 95.0


def test_retry_5xx(stub):
    stub.script((503, {}, b""))
    result, _ = _send(stub, attempt=3)
    assert result.outcome == "retry"
    assert result.retry_after_s == push_sender.backoff_s(3) == 32.0


def test_retry_408_request_timeout(stub):
    # Finding #1040: a 408 is the push service giving up on the request —
    # a server-side timeout, not a client error on our deterministic
    # request — so it retries on the backoff schedule like a 5xx.
    stub.script((408, {}, b""))
    result, _ = _send(stub, attempt=1)
    assert result.outcome == "retry"
    assert result.http_status == 408
    assert result.retry_after_s == push_sender.backoff_s(1) == 2.0


@pytest.mark.parametrize("status", [400, 401, 413, 418, 422])
def test_dead_letter_client_errors(stub, status):
    stub.script((status, {}, b""))
    result, _ = _send(stub)
    assert result.outcome == "dead-letter", status
    assert result.http_status == status
    assert result.retry_after_s is None


def test_redirect_never_followed(stub):
    stub.script((302, {"Location": "https://evil.example/elsewhere"}, b""))
    result, _ = _send(stub)
    assert result.outcome == "dead-letter"
    assert result.http_status == 302
    assert len(stub.server.requests) == 1, "redirect must not be followed"


@pytest.mark.parametrize("exc", [
    ConnectionError("refused"),
    socket.timeout("timed out"),
    socket.gaierror("dns fail"),
    ssl.SSLError("tls fail"),
    http.client.BadStatusLine("garbage"),
])
def test_transport_error_retries(stub, exc):
    def boom(**kw):
        raise exc
    result, _ = _send(stub, transport=boom, attempt=1)
    assert result.outcome == "retry", type(exc).__name__
    assert result.http_status is None
    assert result.retry_after_s == push_sender.backoff_s(1) == 2.0


def test_backoff_schedule():
    assert push_sender.backoff_s(1) == 2.0
    assert push_sender.backoff_s(2) == 8.0
    assert push_sender.backoff_s(3) == 32.0
    assert push_sender.backoff_s(4) == 128.0
    assert push_sender.backoff_s(5) == 300.0  # capped
    assert push_sender.backoff_s(99) == 300.0
    with pytest.raises(ValueError):
        push_sender.backoff_s(0)


def test_parse_retry_after():
    assert push_sender.parse_retry_after(None) is None
    assert push_sender.parse_retry_after("") is None
    assert push_sender.parse_retry_after("30") == 30.0
    assert push_sender.parse_retry_after("99999") == push_sender.RETRY_AFTER_MAX_S
    assert push_sender.parse_retry_after("garbage") is None
    past = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(1000))
    assert push_sender.parse_retry_after(past, now=2000.0) == 0.0


# ---------------------------------------------------------------------------
# Fail-closed validation
# ---------------------------------------------------------------------------


def test_cleartext_endpoint_refused(stub):
    sub = _subscription()
    sub["endpoint"] = "http://push.example.com/wp/x"
    with pytest.raises(ValueError):
        _send(stub, sub=sub)
    assert stub.server.requests == []


def test_endpoint_userinfo_refused(stub):
    sub = _subscription()
    sub["endpoint"] = "https://user:pass@push.example.com/wp/x"
    with pytest.raises(ValueError):
        _send(stub, sub=sub)
    sub["endpoint"] = "https://@push.example.com/wp/x"  # empty userinfo
    with pytest.raises(ValueError):
        _send(stub, sub=sub)
    assert stub.server.requests == []


def test_endpoint_control_chars_and_unicode_refused(stub):
    # Fail fast, before any crypto — these would otherwise surface as
    # http.client errors after the ECDH work.
    for bad in ("https://push.example.com/wp/\x01",
                "https://push.example.com/wörld",
                "https://push.example.com/wp/x\n"):
        sub = _subscription()
        sub["endpoint"] = bad
        with pytest.raises(ValueError):
            _send(stub, sub=sub)
    assert stub.server.requests == []


def test_endpoint_query_preserved(stub):
    result, _ = _send(stub, sub=_subscription(query="x=1&y=2"))
    assert result.outcome == "accepted"
    assert stub.server.requests[0]["path"] == "/wp/abc123?x=1&y=2"
    assert stub.server.targets == [("push.example.com", 443, "/wp/abc123?x=1&y=2")]


def test_ipv6_endpoint_aud_bracketed(stub):
    vapid_priv, vapid_pub = _vapid_keys()
    sub = _subscription(endpoint_host="[2001:db8::1]", endpoint_port=8443)
    result, _ = _send(stub, sub=sub, vapid_priv=vapid_priv, vapid_pub=vapid_pub)
    assert result.outcome == "accepted"
    claims = _jwt_claims(stub.server.requests[0]["headers"]["authorization"])
    assert claims["aud"] == "https://[2001:db8::1]:8443"


def test_explicit_default_port_normalized(stub):
    sub = _subscription(endpoint_port=443)
    result, _ = _send(stub, sub=sub)
    assert result.outcome == "accepted"
    claims = _jwt_claims(stub.server.requests[0]["headers"]["authorization"])
    assert claims["aud"] == "https://push.example.com"


def test_bad_subscription_keys(stub):
    sub = _subscription()
    sub["p256dh"] = _b64url(b"short")
    with pytest.raises(ValueError):
        _send(stub, sub=sub)
    sub = _subscription()
    sub["auth"] = _b64url(b"short")
    with pytest.raises(ValueError):
        _send(stub, sub=sub)
    with pytest.raises(ValueError):
        _send(stub, sub={"endpoint": "https://x.example/"})
    assert stub.server.requests == []


def test_bad_vapid_keys(stub):
    sub = _subscription()
    vapid_priv, vapid_pub = _vapid_keys()
    n_bytes = push_crypto._N.to_bytes(32, "big")  # d must be < N
    for priv, pub in [(b"\x00" * 32, vapid_pub), (vapid_priv, b"\x04" + b"\x00" * 64),
                      (b"short", vapid_pub), (vapid_priv, b"short"),
                      (n_bytes, vapid_pub), (b"\xff" * 32, vapid_pub)]:
        with pytest.raises(ValueError):
            push_sender.send_push(
                subscription=sub, plaintext=b'{"a":1}',
                vapid_private_key=priv, vapid_public_key=pub,
                vapid_subject="mailto:ops@example.com", ttl_s=600, now=1.0,
                transport=_stub_transport(stub))


def test_oversized_plaintext_rejected_before_network(stub):
    with pytest.raises(ValueError):
        _send(stub, plaintext=b"x" * 2000)
    assert stub.server.requests == []


def test_record_size_boundary(stub):
    # RFC 8291 §4: rs > len(plaintext)+17 — with rs=1024, len 1007
    # rejects (1007+17 = 1024, not strictly less) and 1006 passes.
    with pytest.raises(ValueError):
        _send(stub, plaintext=b"x" * 1007)
    assert stub.server.requests == []
    result, _ = _send(stub, plaintext=b"x" * 1006)
    assert result.outcome == "accepted"


def test_empty_plaintext_rejected(stub):
    with pytest.raises(ValueError):
        _send(stub, plaintext=b"")


def test_ttl_header_bounds(stub):
    with pytest.raises(ValueError):
        _send(stub, ttl_s=0)
    with pytest.raises(ValueError):
        _send(stub, ttl_s=90000)
    with pytest.raises(ValueError):
        _send(stub, vapid_subject="")
    with pytest.raises(ValueError):
        _send(stub, ttl_s=True)  # bool is not an int here


def test_ttl_header_value(stub):
    result, _ = _send(stub, ttl_s=300)
    assert result.outcome == "accepted"
    assert stub.server.requests[0]["headers"]["ttl"] == "300"


# ---------------------------------------------------------------------------
# Finding 7: salt discipline + finding 5: record_size pin
# ---------------------------------------------------------------------------


def test_no_caller_salt_parameter():
    assert "salt" not in inspect.signature(push_sender.send_push).parameters


def test_each_send_uses_fresh_salt(stub):
    _send(stub)
    _send(stub)
    bodies = [r["body"] for r in stub.server.requests]
    assert len(bodies) == 2
    assert bodies[0] != bodies[1]
    # salts (first 16 bytes) differ
    assert bodies[0][:16] != bodies[1][:16]


# ---------------------------------------------------------------------------
# Production transport TLS policy (compensating check for the stub's
# plain-HTTP difference)
# ---------------------------------------------------------------------------


def test_default_transport_enforces_tls():
    seen = {}

    class FakeSock:
        def settimeout(self, t):
            seen["read_timeout"] = t

    class FakeConn:
        def __init__(self, host, port, timeout=None, context=None):
            seen.update(host=host, port=port, timeout=timeout, context=context)
            # Plain attribute (not a property): _default_transport swaps
            # in its deadline proxy for the header phase and restores it.
            self.sock = FakeSock()

        def request(self, method, path, body=None, headers=None):
            seen.update(method=method, path=path, headers=headers)

        def getresponse(self):
            class R:
                status = 201

                def getheaders(self):
                    # Mixed-case, as a real server sends them — the
                    # transport must lowercase before classifying.
                    return [("Retry-After", "30"), ("X-Mixed", "v")]

                def read(self):
                    return b"SHOULD-NOT-BE-READ"
            return R()

        def close(self):
            seen["closed"] = True

    with mock.patch.object(http.client, "HTTPSConnection", FakeConn):
        status, headers, body = push_sender._default_transport(
            host="push.example.com", port=443, path="/wp/x",
            headers={"TTL": "600", "Authorization": "vapid t=abc, k=def"},
            body=b"body")

    assert status == 201
    ctx = seen["context"]
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.check_hostname is True
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert seen["method"] == "POST"
    assert seen["path"] == "/wp/x"
    assert seen["timeout"] == push_sender.CONNECT_TIMEOUT_S
    assert seen["read_timeout"] == push_sender.READ_TIMEOUT_S
    assert seen["closed"] is True
    # Response headers are lowercased (so "Retry-After" classifies),
    # request headers and body pass through untouched...
    assert headers == {"retry-after": "30", "x-mixed": "v"}
    assert seen["headers"]["Authorization"] == "vapid t=abc, k=def"
    # ...and the response body is deliberately NOT read (the caller
    # discards it; an unbounded read is a memory-exhaustion vector).
    assert body == b""


# ---------------------------------------------------------------------------
# #1039: total deadline on the response-header read
# ---------------------------------------------------------------------------


class _DripServer:
    """A push-service stub that drips the response one byte per 9 s —
    inside the 10 s per-recv timeout, so without a total deadline the
    header read would never finish."""

    DRIP_INTERVAL_S = 9.0

    def __init__(self):
        self._done = threading.Event()
        self.lsock = socket.socket()
        self.lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.lsock.bind(("127.0.0.1", 0))
        self.lsock.listen(1)
        self.thread = threading.Thread(target=self._serve, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self._done.set()
        try:
            self.lsock.close()
        except OSError:
            pass
        self.thread.join(timeout=10)

    @property
    def port(self):
        return self.lsock.getsockname()[1]

    def _serve(self):
        try:
            conn, _ = self.lsock.accept()
        except OSError:
            return
        try:
            # Read the request (headers + declared body) so the client
            # never blocks on send.
            f = conn.makefile("rb")
            length = 0
            while True:
                line = f.readline()
                if not line or line in (b"\r\n", b"\n"):
                    break
                if line.lower().startswith(b"content-length:"):
                    length = int(line.split(b":", 1)[1])
            while length > 0:
                chunk = f.read(min(length, 65536))
                if not chunk:
                    break
                length -= len(chunk)
            # Drip response bytes forever (or until the client goes away).
            stream = b"HTTP/1.1 201 Created\r\nContent-Length: 0\r\n\r\n"
            i = 0
            while not self._done.is_set():
                try:
                    conn.sendall(stream[i:i + 1])
                except OSError:
                    break
                i = (i + 1) % len(stream)
                self._done.wait(self.DRIP_INTERVAL_S)
        finally:
            try:
                conn.close()
            except OSError:
                pass


class _DripConn:
    """A stand-in for ``http.client.HTTPSConnection`` that opens a real
    plain socket to the drip server but runs the production header-read
    path: ``http.client.HTTPResponse`` over ``sock.makefile()`` — exactly
    what ``_default_transport`` feeds its deadline proxy."""

    def __init__(self, server):
        self._server = server

    def __call__(self, host, port, timeout=None, context=None):
        server = self._server

        class Conn:
            def __init__(self):
                # Plain attribute (not a property): _default_transport
                # swaps in its deadline proxy for the header phase.
                self.sock = socket.create_connection(
                    ("127.0.0.1", server.port), timeout=timeout)

            def request(self, method, path, body=None, headers=None):
                lines = [f"{method} {path} HTTP/1.1", "Host: drip.invalid"]
                for k, v in (headers or {}).items():
                    lines.append(f"{k}: {v}")
                raw = ("\r\n".join(lines) + "\r\n\r\n").encode("ascii")
                self.sock.sendall(raw + (body or b""))

            def getresponse(self):
                # Same construction the real HTTPSConnection performs —
                # the deadline proxy is already installed as self.sock,
                # and begin() is where the header read happens.
                resp = http.client.HTTPResponse(self.sock, method="POST")
                resp.begin()
                return resp

            def close(self):
                try:
                    self.sock.close()
                except OSError:
                    pass

        return Conn()


def test_response_header_total_deadline():
    """#1039: the production transport's response-header read carries a
    total deadline — the drip server answers inside the per-recv window
    forever, so only the deadline can stop the read."""
    with _DripServer() as server:
        with mock.patch.object(http.client, "HTTPSConnection",
                               _DripConn(server)):
            start = time.monotonic()
            with pytest.raises(socket.timeout):
                push_sender._default_transport(
                    host="drip.invalid", port=443, path="/",
                    headers={}, body=b"x")
            elapsed = time.monotonic() - start
    # ~30 s, not ~10 s (per-recv never fires — bytes arrive every 9 s)
    # and nowhere near the ~200 s the unbounded drip would take.
    assert 25 <= elapsed < 60, f"deadline did not bound the drip: {elapsed:.1f}s"
    assert push_sender.RESPONSE_DEADLINE_S == 30.0


def test_dripping_push_service_classifies_retry():
    """#1039 end-to-end: the deadline expiry surfaces as a transport
    error, which send_push classifies retry (the push service may come
    back) — never a hang, never a terminal misclassification."""
    with _DripServer() as server:
        sub = _subscription()
        vapid_priv, vapid_pub = _vapid_keys()
        with mock.patch.object(http.client, "HTTPSConnection",
                               _DripConn(server)):
            start = time.monotonic()
            result = push_sender.send_push(
                subscription=sub, plaintext=b'{"aid":"a1"}',
                vapid_private_key=vapid_priv, vapid_public_key=vapid_pub,
                vapid_subject="mailto:ops@example.com", ttl_s=600,
                attempt=1, now=1_700_000_000.0, transport=None)
            elapsed = time.monotonic() - start
    assert result.outcome == "retry"
    assert result.http_status is None
    assert result.retry_after_s == push_sender.backoff_s(1)
    assert 25 <= elapsed < 60, f"deadline did not bound the drip: {elapsed:.1f}s"


# ---------------------------------------------------------------------------
# #428 §4 retirement mapping
# ---------------------------------------------------------------------------


def test_acceptance_record(stub):
    result, sub = _send(stub, now=1_700_000_100.0)
    assert result.outcome == "accepted"
    record = push_sender.acceptance_fields(
        result, subscription_ref="owner1/box7/phone", sent_at=1_700_000_100.0)
    assert isinstance(record, MappingProxyType)
    assert dict(record) == {
        "subscription_ref": "owner1/box7/phone",
        "outcome": "accepted",
        "http_status": 201,
        "sent_at": 1_700_000_100.0,
        "latency_ms": result.latency_ms,
    }
    with pytest.raises(TypeError):
        record["endpoint"] = "https://push.example.com"  # immutable


def test_acceptance_record_rejects_non_accepted(stub):
    stub.script((500, {}, b""))
    result, _ = _send(stub)
    assert result.outcome == "retry"
    with pytest.raises(ValueError):
        push_sender.acceptance_fields(result, subscription_ref="r", sent_at=1.0)
