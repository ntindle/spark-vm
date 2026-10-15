#!/usr/bin/env python3
"""Tests for hosted/relay_dial_prober.py — #1414 R2a dial prober core.

Acceptance per the issue: unit-testable against a fake relay listener +
fake provider state; probe frames never journaled; handshake-only provable
(no auth attempted); §4 no-inbound discipline intact (the prober dials
outbound to the tenant-facing listener only — every test dials
127.0.0.1).
"""

import base64
import hashlib
import os
import socket
import socketserver
import struct
import threading
import time

import pytest

import relay_dial_prober as prober
import relay_liveness as rl

# ---------------------------------------------------------------------------
# Fake relay listener
# ---------------------------------------------------------------------------

# Fixed DH group for the fake (the prober completes no DH, so any p > 2
# works; the fake never validates the client's e beyond range).
_FAKE_P = 2**512 - 381
_FAKE_G = 2


def _rsa_blob(seed):
    """A well-formed (not real) ssh-rsa public-key blob, fixed per seed."""
    n = int.from_bytes(hashlib.sha256(seed).digest() * 8, "big") | (1 << 2047)
    e = 65537
    return _pkt_string(b"ssh-rsa") + _pkt_mpint(e) + _pkt_mpint(n)


def _pkt_string(b):
    return struct.pack(">I", len(b)) + b


def _pkt_mpint(n):
    raw = n.to_bytes((n.bit_length() + 7) // 8 or 1, "big")
    if raw[0] & 0x80:
        raw = b"\x00" + raw
    return struct.pack(">I", len(raw)) + raw


def _pkt_name_list(names):
    return _pkt_string(b",".join(names))


def _pkt(payload):
    pad_len = 8 - ((5 + len(payload)) % 8)
    if pad_len < 4:
        pad_len += 8
    packet_len = 1 + len(payload) + pad_len
    return (
        struct.pack(">I", packet_len)
        + struct.pack("B", pad_len)
        + payload
        + b"\x00" * pad_len
    )


def _fake_kexinit(kex_names):
    cookie = b"\x01" * 16
    payload = (
        struct.pack("B", 20)
        + cookie
        + _pkt_name_list(kex_names)
        + _pkt_name_list([b"ssh-rsa"])
        + _pkt_name_list([b"aes128-ctr"])
        + _pkt_name_list([b"aes128-ctr"])
        + _pkt_name_list([b"hmac-sha2-256"])
        + _pkt_name_list([b"hmac-sha2-256"])
        + _pkt_name_list([b"none"])
        + _pkt_name_list([b"none"])
        + _pkt_name_list([b""])
        + _pkt_name_list([b""])
        + struct.pack("B", 0)
        + struct.pack(">I", 0)
    )
    return _pkt(payload)


class _FakeRelay(socketserver.BaseRequestHandler):
    """Fake relay listener with a buffered reader.

    The prober sends its ident line and KEXINIT back-to-back; TCP may
    coalesce them into one segment, so banner and packet reads share one
    buffer — bytes already received are never discarded (an earlier
    draft dropped the post-banner remainder and deadlocked).
    """

    def handle(self):
        srv = self.server
        srv.connections += 1
        conn = self.request
        conn.settimeout(10)
        self._buf = b""
        try:
            self._run(conn)
        except (EOFError, socket.timeout, OSError, ValueError):
            pass
        finally:
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            conn.close()

    def _recv_exact(self, conn, n):
        while len(self._buf) < n:
            chunk = conn.recv(n - len(self._buf))
            if not chunk:
                raise EOFError("eof")
            self._buf += chunk
        out, self._buf = self._buf[:n], self._buf[n:]
        return out

    def _read_banner(self, conn):
        while b"\n" not in self._buf:
            chunk = conn.recv(256)
            if not chunk:
                raise EOFError("eof")
            self._buf += chunk
            if len(self._buf) > 1024:
                raise ValueError("banner too long")
        line, self._buf = self._buf.split(b"\n", 1)
        return line

    def _read_packet(self, conn):
        hdr = self._recv_exact(conn, 4)
        (packet_len,) = struct.unpack(">I", hdr)
        body = self._recv_exact(conn, packet_len)
        pad_len = body[0]
        return body[1 : packet_len - pad_len]

    def _run(self, conn):
        srv = self.server
        scenario = srv.scenario
        if scenario == "accept_close":
            return
        if scenario == "garbage_banner":
            conn.sendall(b"NOT-SSH-PROTOCOL\r\n")
            return
        if scenario == "legacy_banner":
            conn.sendall(b"SSH-1.99-legacy\r\n")
            return
        if scenario == "trickle":
            # A hostile/tarpit relay: dribbles one byte at a time, never
            # a full line — the absolute I/O deadline must bound this.
            import time as _t

            try:
                while True:
                    conn.sendall(b"X")
                    _t.sleep(0.9)
            except OSError:
                return
        if scenario == "silent":
            import time as _t

            _t.sleep(5)
            return
        client_banner = None
        # Version exchange: the server sends its banner first (RFC 4253
        # §4.2 — either side may send first; the prober reads first).
        conn.sendall(b"SSH-2.0-FakeRelay_1.0\r\n")
        client_banner = self._read_banner(conn)
        srv.client_banners.append(client_banner)
        if scenario == "server_disconnect":
            self._read_packet(conn)  # client KEXINIT
            disc = struct.pack("B", 1) + struct.pack(">I", 2)
            disc += _pkt_string(b"going away") + _pkt_string(b"")
            conn.sendall(_pkt(disc))
            return
        # Handshake scenarios: ok / wrong_key / no_group_exchange
        payload = self._read_packet(conn)  # client KEXINIT
        srv.received.append(payload[0] if payload else -1)
        if scenario == "no_group_exchange":
            kex = [b"diffie-hellman-group14-sha256", b"ext-info-c"]
        else:
            kex = [b"diffie-hellman-group-exchange-sha256"]
        conn.sendall(_fake_kexinit(kex))
        if scenario == "no_group_exchange":
            # Prober should give up here; drain until it closes.
            try:
                while True:
                    p = self._read_packet(conn)
                    srv.received.append(p[0] if p else -1)
            except EOFError:
                return
        payload = self._read_packet(conn)  # GEX_REQUEST (34)
        srv.received.append(payload[0] if payload else -1)
        group = struct.pack("B", 31) + _pkt_mpint(_FAKE_P) + _pkt_mpint(_FAKE_G)
        conn.sendall(_pkt(group))
        payload = self._read_packet(conn)  # GEX_INIT (32)
        srv.received.append(payload[0] if payload else -1)
        (ln,) = struct.unpack(">I", payload[1:5])
        srv.gex_e = int.from_bytes(payload[5 : 5 + ln], "big")
        blob = srv.host_key_blob
        reply = (
            struct.pack("B", 33)
            + _pkt_string(blob)
            + _pkt_mpint(12345)
            + _pkt_string(b"fakesig")
        )
        conn.sendall(_pkt(reply))
        try:
            while True:
                p = self._read_packet(conn)
                srv.received.append(p[0] if p else -1)
        except EOFError:
            return


class _FakeRelayServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


@pytest.fixture()
def fake_relay():
    srv = _FakeRelayServer(("127.0.0.1", 0), _FakeRelay)
    srv.scenario = "ok"
    srv.connections = 0
    srv.client_banners = []
    srv.received = []
    srv.gex_e = None
    srv.host_key_blob = _rsa_blob(b"r2a-ok-key")
    t = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05})
    t.daemon = True
    t.start()
    yield srv
    srv.shutdown()
    srv.server_close()


def _pin_of(blob):
    return prober._fingerprint_of(blob)


def _probe_kwargs(srv, **over):
    kw = dict(
        vm_id="vm-test-1",
        relay_host="127.0.0.1",
        relay_port=srv.server_address[1],
        pinned_fingerprint=_pin_of(srv.host_key_blob),
        provider_state_fn=lambda: "running",
        connect_timeout_s=3.0,
        io_timeout_s=3.0,
    )
    kw.update(over)
    return kw


# ---------------------------------------------------------------------------
# Taxonomy + discriminator pins
# ---------------------------------------------------------------------------


def test_outcome_taxonomy_verbatim():
    assert prober.OUTCOMES == {
        "path_ok",
        "relay_defect",
        "cert_defect",
        "box_leg_defect",
        "provider_not_running",
    }


def test_prober_ident_is_ssh2_client_string():
    assert prober.PROBER_IDENT == "SSH-2.0-sparkvm-relay-prober"
    assert prober.PROBER_IDENT.startswith("SSH-2.0-")


# ---------------------------------------------------------------------------
# Happy path + cert defect
# ---------------------------------------------------------------------------


def test_path_ok(fake_relay):
    r = prober.probe(**_probe_kwargs(fake_relay))
    assert r.outcome == "path_ok"
    assert r.detail["observed_fingerprint"] == _pin_of(
        fake_relay.host_key_blob
    )
    assert r.detail["server_banner"] == "SSH-2.0-FakeRelay_1.0"
    assert r.detail["prober_ident"] == prober.PROBER_IDENT
    assert r.detail["host_key_algo"] == "ssh-rsa"
    assert isinstance(r.detail["elapsed_ms"], int)
    assert r.detail["elapsed_ms"] >= 0


def test_cert_defect_on_key_mismatch(fake_relay):
    other = _rsa_blob(b"r2a-other-key")
    r = prober.probe(
        **_probe_kwargs(
            fake_relay, pinned_fingerprint=_pin_of(other)
        )
    )
    assert r.outcome == "cert_defect"
    assert r.detail["observed_fingerprint"] == _pin_of(
        fake_relay.host_key_blob
    )
    # The pin itself never echoes in detail (nothing secret to leak,
    # but the contract is pin-in, observed-out).
    assert "pinned_fingerprint" not in r.detail


def test_client_banner_carries_discriminator(fake_relay):
    prober.probe(**_probe_kwargs(fake_relay))
    assert fake_relay.client_banners
    # The ident line is CRLF-terminated per RFC 4253 §4.2; the fake's
    # _read_banner splits on \n only, so strip the trailing \r here.
    assert all(b.rstrip(b"\r") == prober.PROBER_IDENT.encode("ascii")
               for b in fake_relay.client_banners)


def test_handshake_only_no_newkeys_no_auth(fake_relay):
    r = prober.probe(**_probe_kwargs(fake_relay))
    assert r.outcome == "path_ok"
    # The fake records from its handler thread; probe() returns once the
    # prober has closed, but the handler may not have consumed the final
    # DISCONNECT yet — poll briefly for the transcript to settle.
    deadline = time.monotonic() + 5.0
    while len(fake_relay.received) < 4 and time.monotonic() < deadline:
        time.sleep(0.01)
    received = fake_relay.received
    # KEXINIT(20), GEX_REQUEST(34), GEX_INIT(32), DISCONNECT(1) — and
    # nothing else, in exactly this order.
    assert received == [20, 34, 32, 1]
    assert 21 not in received  # NEWKEYS never sent
    assert not any(50 <= m <= 79 for m in received)  # no USERAUTH_*


def test_gex_init_e_in_range(fake_relay):
    prober.probe(**_probe_kwargs(fake_relay))
    e = fake_relay.gex_e
    assert e is not None
    assert 1 < e < _FAKE_P - 1


# ---------------------------------------------------------------------------
# Defect taxonomy
# ---------------------------------------------------------------------------


def _closed_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_relay_defect_connection_refused(fake_relay):
    r = prober.probe(
        **_probe_kwargs(fake_relay, relay_port=_closed_port())
    )
    assert r.outcome == "relay_defect"
    assert "error" in r.detail


def test_relay_defect_unresolvable_host(fake_relay, monkeypatch):
    # Hermetic: this sandbox's DNS wildcard-resolves everything
    # (198.18.10.223), so "unresolvable" is simulated by making the
    # connect itself raise gaierror — the unit under test is the
    # outcome mapping, not the resolver.
    def _no_dns(*a, **k):
        raise socket.gaierror(
            socket.EAI_NONAME, "Name or service not known"
        )

    monkeypatch.setattr(prober.socket, "create_connection", _no_dns)
    r = prober.probe(
        **_probe_kwargs(
            fake_relay,
            relay_host="relay-definitely-not-here.invalid",
            connect_timeout_s=2.0,
        )
    )
    assert r.outcome == "relay_defect"
    assert fake_relay.connections == 0


def test_box_leg_defect_garbage_banner(fake_relay):
    fake_relay.scenario = "garbage_banner"
    r = prober.probe(**_probe_kwargs(fake_relay))
    assert r.outcome == "box_leg_defect"
    assert "banner" in r.detail["error"]


def test_box_leg_defect_legacy_banner(fake_relay):
    # A non-SSH-2.0 banner (something else bound the relay port): the
    # version gate, not the no-banner path.
    fake_relay.scenario = "legacy_banner"
    r = prober.probe(**_probe_kwargs(fake_relay))
    assert r.outcome == "box_leg_defect"
    assert r.detail["error"] == "banner_not_ssh2"


def test_box_leg_defect_trickle_server_bounded_by_deadline(fake_relay):
    # A tarpit relay dribbling one byte per 0.9s would stretch a
    # per-recv-only timeout without bound; the absolute deadline
    # (connect_timeout_s + io_timeout_s) must cap the probe.
    fake_relay.scenario = "trickle"
    t0 = time.monotonic()
    r = prober.probe(
        **_probe_kwargs(
            fake_relay, connect_timeout_s=5.0, io_timeout_s=1.0
        )
    )
    elapsed = time.monotonic() - t0
    assert r.outcome == "box_leg_defect"
    assert r.detail["error"] == "io_deadline"
    assert elapsed < 12.0  # deadline is 6s; 2x slack for CI


def test_box_leg_defect_accept_then_close(fake_relay):
    fake_relay.scenario = "accept_close"
    r = prober.probe(**_probe_kwargs(fake_relay))
    assert r.outcome == "box_leg_defect"


def test_box_leg_defect_no_group_exchange(fake_relay):
    fake_relay.scenario = "no_group_exchange"
    r = prober.probe(**_probe_kwargs(fake_relay))
    assert r.outcome == "box_leg_defect"
    assert r.detail["error"] == "kex_mismatch"


def test_box_leg_defect_silent_server(fake_relay):
    fake_relay.scenario = "silent"
    r = prober.probe(**_probe_kwargs(fake_relay, io_timeout_s=1.0))
    assert r.outcome == "box_leg_defect"


def test_box_leg_defect_server_disconnect(fake_relay):
    fake_relay.scenario = "server_disconnect"
    r = prober.probe(**_probe_kwargs(fake_relay))
    assert r.outcome == "box_leg_defect"
    assert "unexpected_msg_1" in r.detail["error"]


# ---------------------------------------------------------------------------
# Provider-state stand-down (D-RL2-4; fake driver)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "state",
    ["suspended", "suspending", "waking", "stopping", "stopped",
     "destroyed", "failed", "provisioning", "unrecognized-state"],
)
def test_provider_not_running_stands_down_without_dialing(
    fake_relay, state
):
    r = prober.probe(
        **_probe_kwargs(
            fake_relay, provider_state_fn=lambda s=state: s
        )
    )
    assert r.outcome == "provider_not_running"
    assert r.detail["provider_state"] == state
    assert r.detail["dialed"] is False
    assert fake_relay.connections == 0


def test_provider_state_fn_raising_propagates(fake_relay):
    def boom():
        raise RuntimeError("driver exploded")

    with pytest.raises(RuntimeError):
        prober.probe(**_probe_kwargs(fake_relay, provider_state_fn=boom))


# ---------------------------------------------------------------------------
# Fail-closed validation (before any network)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kw", [{"connect_timeout_s": 0},
                                 {"io_timeout_s": -1.0}])
def test_nonpositive_timeouts_rejected(fake_relay, kw):
    with pytest.raises(ValueError, match="must be positive"):
        prober.probe(**_probe_kwargs(fake_relay, **kw))
    assert fake_relay.connections == 0


@pytest.mark.parametrize("bad", ["", "abc", "MD5:aa:bb:cc", "SHA256:!!!",
                                 "SHA256:" + "A" * 43 + " ",
                                 "sha256:" + "A" * 43,
                                 # Valid base64 shape, wrong length: 42
                                 # chars decode to 31 bytes, not 32.
                                 "SHA256:" + "A" * 42])
def test_malformed_pinned_fingerprint_rejected(fake_relay, bad):
    with pytest.raises(ValueError):
        prober.probe(**_probe_kwargs(fake_relay,
                                     pinned_fingerprint=bad))
    assert fake_relay.connections == 0


def test_vm_id_must_be_nonempty_str(fake_relay):
    with pytest.raises(ValueError):
        prober.probe(**_probe_kwargs(fake_relay, vm_id=""))
    with pytest.raises(ValueError):
        prober.probe(**_probe_kwargs(fake_relay, vm_id="a\x00b"))


@pytest.mark.parametrize("bad_port", [0, 70000, -1, "22", None])
def test_relay_port_validated(fake_relay, bad_port):
    with pytest.raises(ValueError):
        prober.probe(**_probe_kwargs(fake_relay, relay_port=bad_port))


# ---------------------------------------------------------------------------
# Identity-marker discriminator vs the R1 journal (design §2)
# ---------------------------------------------------------------------------


def _frame(**over):
    f = dict(
        session_id="sess-1",
        vm_id="vm-test-1",
        opened_at=1700000000.0,
        last_bytes_at=1700000000.0,
        closed_at=None,
        close_cause=None,
        hostkey_verified=True,
        bytes_in=0,
        bytes_out=0,
    )
    f.update(over)
    return f


def test_prober_marked_frame_dropped_by_journal(tmp_path, monkeypatch):
    monkeypatch.setenv("RELAY_SESSION_JOURNAL", str(tmp_path / "j.jsonl"))
    # The prober's discriminator (client ident) is what the relay daemon
    # uses to mark frames; the journal drops anything marked.
    assert rl.emit_frame(prober=True, **_frame()) == "dropped"
    assert rl.emit_frame(**_frame(session_id="sess-2")) == "journaled"
    live = rl.relay_session_liveness("vm-test-1")
    assert live["session_id"] == "sess-2"
