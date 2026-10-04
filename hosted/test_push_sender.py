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


def _subscription(endpoint_host="push.example.com", endpoint_port=None):
    priv, pub = push_crypto.generate_keypair()
    auth = secrets.token_bytes(16)
    endpoint = f"https://{endpoint_host}"
    if endpoint_port:
        endpoint += f":{endpoint_port}"
    endpoint += "/wp/abc123"
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
        # test_default_transport_enforces_tls instead.
        conn = http.client.HTTPConnection("127.0.0.1", stub.port, timeout=5)
        try:
            conn.request("POST", "/", body=body, headers=headers)
            resp = conn.getresponse()
            return resp.status, {k.lower(): v for k, v in resp.getheaders()}, resp.read()
        finally:
            conn.close()
    return transport


def _send(stub, sub=None, plaintext=b'{"aid":"a1","ttl_s":600,"summary":"hi"}',
          ttl_s=600, attempt=1, now=1_700_000_000.0, transport=None,
          vapid_subject="mailto:ops@example.com", **kw):
    sub = sub if sub is not None else _subscription()
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


def test_accepted_202(stub):
    stub.script((202, {}, b""))
    result, _ = _send(stub)
    assert result.outcome == "accepted"
    assert result.http_status == 202


def test_vapid_policy_exp_aud_k(stub):
    result, sub = _send(stub, now=1_700_000_000.0)
    assert result.outcome == "accepted"
    h = stub.server.requests[0]["headers"]
    vapid_priv, vapid_pub = _vapid_keys()
    # Re-derive what the header must carry: aud = endpoint origin.
    claims = _jwt_claims(h["authorization"])
    assert claims["aud"] == "https://push.example.com"
    assert claims["exp"] == 1_700_000_000 + push_sender.VAPID_EXPIRY_S
    assert claims["exp"] - 1_700_000_000 <= 24 * 3600
    assert claims["sub"] == "mailto:ops@example.com"
    k_param = h["authorization"].split(", k=")[1]
    # k= must be *a* 65-octet uncompressed point (the current VAPID key).
    raw = base64.urlsafe_b64decode(k_param + "=" * (-len(k_param) % 4))
    assert len(raw) == 65 and raw[:1] == b"\x04"


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


def test_transport_error_retries(stub):
    def boom(**kw):
        raise ConnectionError("refused")
    result, _ = _send(stub, transport=boom, attempt=1)
    assert result.outcome == "retry"
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
    assert stub.server.requests == []


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
    for priv, pub in [(b"\x00" * 32, vapid_pub), (vapid_priv, b"\x04" + b"\x00" * 64),
                      (b"short", vapid_pub), (vapid_priv, b"short")]:
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

    class FakeConn:
        def __init__(self, host, port, timeout=None, context=None):
            seen.update(host=host, port=port, timeout=timeout, context=context)

        def request(self, method, path, body=None, headers=None):
            seen.update(method=method, path=path, headers=headers)

        @property
        def sock(self):
            class S:
                def settimeout(self, t):
                    seen["read_timeout"] = t
            return S()

        def getresponse(self):
            class R:
                status = 201

                def getheaders(self):
                    return []

                def read(self):
                    return b""
            return R()

        def close(self):
            seen["closed"] = True

    with mock.patch.object(http.client, "HTTPSConnection", FakeConn):
        status, headers, body = push_sender._default_transport(
            host="push.example.com", port=443, path="/wp/x",
            headers={"TTL": "600"}, body=b"body")

    assert status == 201
    ctx = seen["context"]
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.check_hostname is True
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert seen["method"] == "POST"
    assert seen["timeout"] == push_sender.CONNECT_TIMEOUT_S
    assert seen["read_timeout"] == push_sender.READ_TIMEOUT_S
    assert seen["closed"] is True


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
