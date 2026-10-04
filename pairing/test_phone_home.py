"""Tests for spark-pair.py phone-home (issues #959 S5a + #976 S5b: box-side
WSS client).

A stub control plane speaks the wire-spec subset (upgrade handshake,
hello/welcome, keepalive, the close taxonomy) over a loopback TCP socket;
every test proves a spec property against it: the generation fence, the
close-code reconnect policy, the upgrade-401 rotate-once path, the
no-redirect upgrade, backoff bounds, and the credential-never-in-logs
discipline. S5b wires `command` frames into the #874 ingest executor
with socket `command_ack`s (the §3.3 decision — _http is rigged to
explode in the S5b tests, so any HTTPS ack would fail); untrusted
command frames are logged and never executed.
"""
import base64
import hashlib
import io
import json
import os
import socket
import struct
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import spark_pair


BOX_ID = "box-test"
TOKEN = "tok-secret-abc123"
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class Ctx:
    """Fake argparse namespace for cmd_phone_home."""
    def __init__(self, tmp_path, **kw):
        self.dir = str(tmp_path / "state")
        self.control = None  # set per test to the stub URL
        for k, v in kw.items():
            setattr(self, k, v)


@pytest.fixture()
def ctx(tmp_path, monkeypatch):
    c = Ctx(tmp_path)
    os.makedirs(c.dir, mode=0o700, exist_ok=True)
    with open(os.path.join(c.dir, "enrollment.json"), "w") as f:
        json.dump({"box_id": BOX_ID, "token": TOKEN,
                   "token_expires_at": int(time.time()) + 3600}, f)
    # Fast, deterministic timing: stub sleeps instead of real ones.
    monkeypatch.setattr(spark_pair, "_WS_PING_INTERVAL", 0.2)
    monkeypatch.setattr(spark_pair, "_WS_READ_TIMEOUT", 1.0)
    sleeps = []
    monkeypatch.setattr(spark_pair, "_ws_sleep",
                        lambda s: sleeps.append(s))
    c.sleeps = sleeps
    spark_pair._PHONE_HOME_STOP = False
    yield c
    spark_pair._PHONE_HOME_STOP = False


# -- stub control plane -------------------------------------------------------
# Speaks just enough of the wire spec to drive the client: the HTTP
# upgrade (scripted 101/401/302/bad-accept), masked client-frame decode,
# unmasked server frames, and auto-pong for client pings.

def _stub_send_frame(conn, payload: bytes, opcode=0x1):
    n = len(payload)
    if n < 126:
        hdr = bytes([0x80 | opcode, n])
    elif n < 65536:
        hdr = bytes([0x80 | opcode, 126]) + struct.pack(">H", n)
    else:
        hdr = bytes([0x80 | opcode, 127]) + struct.pack(">Q", n)
    conn.sendall(hdr + payload)


def _stub_send_json(conn, obj):
    _stub_send_frame(conn,
                     json.dumps(obj, separators=(",", ":")).encode())


def _stub_read_exact(conn, n):
    chunks = []
    while n > 0:
        chunk = conn.recv(n)
        if not chunk:
            raise ConnectionError("client closed")
        chunks.append(chunk)
        n -= len(chunk)
    return b"".join(chunks)


def _stub_read_frame(conn):
    """Read one masked client frame; auto-answer WS pings. Returns
    (opcode, payload)."""
    while True:
        hdr = _stub_read_exact(conn, 2)
        b0, b1 = hdr[0], hdr[1]
        opcode = b0 & 0x0F
        assert b1 & 0x80, "client frames must be masked"
        n = b1 & 0x7F
        if n == 126:
            n = struct.unpack(">H", _stub_read_exact(conn, 2))[0]
        elif n == 127:
            n = struct.unpack(">Q", _stub_read_exact(conn, 8))[0]
        mask = _stub_read_exact(conn, 4)
        payload = _stub_read_exact(conn, n)
        payload = bytes(c ^ mask[i % 4] for i, c in enumerate(payload))
        if opcode == 0x9:  # WS ping → pong
            _stub_send_frame(conn, payload, opcode=0xA)
            continue
        return opcode, payload


class StubDO(threading.Thread):
    """Scripted stub of the plane's phone-home surface.

    conns: per-connection scripts; each is a list of steps:
      ("upgrade-401",) / ("upgrade-302",) / ("upgrade-bad-accept",)
      ("welcome",)            — 101, read hello, send welcome
      ("send", obj)           — send a JSON frame
      ("send-binary", bytes)  — send a binary frame (protocol violation)
      ("send-masked", bytes)  — send a MASKED frame (protocol violation)
      ("expect-pong",)        — read one client frame, assert JSON pong
      ("close", code, extra)  — send close control frame, linger, drop
      ("close-tcp",)          — drop TCP abruptly (transport loss)
      ("ping",)               — send JSON ping, expect JSON pong back
      ("send-ws-ping", bytes) — send a WS-level ping (opcode 0x9)
      ("expect-ws-pong", bytes) — read one frame, assert WS pong + payload
      ("drain", seconds)      — read+record client frames until the deadline
                               (discards nothing; never pongs JSON pings)
      ("send-command", seq, epoch, inner)
                             — send a wire-spec §3.3 command frame with
                               this connection's generation
      ("send-command-as", gen, seq, epoch, inner)
                             — as send-command but with an explicit
                               generation (fence tests)
      ("expect-acks", [seqs])  — read client frames (skipping the client's
                               own periodic JSON pings) until one
                               command_ack per seq in `seqs` arrives;
                               asserts the §3.1 ack shape on each
      ("welcome-raw", obj)    — as step0: read hello, send obj as the first
                               frame instead of a welcome (bad-welcome /
                               close-before-welcome tests)
      ("welcome-dwell", secs) — as step0: read hello, then stall past the
                               client's welcome timeout
    Records per connection: raw upgrade request bytes, decoded hello,
    all client frames (decoded JSON in "frames", raw payloads in
    "frames_raw"), and the Authorization header presence.
    """

    def __init__(self, conns, box_id=BOX_ID):
        super().__init__(daemon=True)
        self.conns = list(conns)
        self.box_id = box_id
        self.records = []
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(5)
        self.sock.settimeout(20)
        self.port = self.sock.getsockname()[1]
        self._ready = threading.Event()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}"

    def run(self):
        self._ready.set()
        try:
            for script in self.conns:
                conn, _ = self.sock.accept()
                conn.settimeout(10)
                try:
                    self._serve(conn, script)
                except (ConnectionError, socket.timeout, OSError):
                    pass
                finally:
                    try:
                        conn.close()
                    except OSError:
                        pass
        finally:
            self.sock.close()

    def _read_http(self, conn):
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = conn.recv(4096)
            if not chunk:
                raise ConnectionError("eof in http")
            buf += chunk
            if len(buf) > 65536:
                raise ConnectionError("http head too large")
        head, _ = buf.split(b"\r\n\r\n", 1)
        return head

    def _serve(self, conn, script):
        rec = {"request": b"", "hello": None, "frames": [],
               "frames_raw": [], "auth_header": None, "upgrade_path": None}
        self.records.append(rec)
        head = self._read_http(conn)
        rec["request"] = head
        lines = head.decode("latin-1").split("\r\n")
        request_line = lines[0]
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()
        rec["auth_header"] = headers.get("authorization")
        rec["upgrade_path"] = request_line.split(" ")[1]
        step0 = script[0]
        if step0[0] == "upgrade-401":
            conn.sendall(b"HTTP/1.1 401 Unauthorized\r\n"
                         b"Content-Length: 0\r\n\r\n")
            return
        if step0[0] == "upgrade-302":
            conn.sendall(b"HTTP/1.1 302 Found\r\n"
                         b"Location: http://evil.test/x\r\n"
                         b"Content-Length: 0\r\n\r\n")
            return
        key = headers.get("sec-websocket-key", "")
        accept = base64.b64encode(
            hashlib.sha1((key + WS_GUID).encode()).digest()).decode()
        if step0[0] == "upgrade-bad-accept":
            accept = "bogus"
        conn.sendall(("HTTP/1.1 101 Switching Protocols\r\n"
                      "Upgrade: websocket\r\n"
                      "Connection: Upgrade\r\n"
                      f"Sec-WebSocket-Accept: {accept}\r\n\r\n").encode())
        if step0[0] == "upgrade-bad-accept":
            return
        if step0[0] == "welcome-dwell":
            # Read hello, then stall past the client's welcome timeout —
            # the client must transport-lost and reconnect, not traceback.
            opcode, payload = _stub_read_frame(conn)
            hello = json.loads(payload.decode())
            rec["hello"] = hello
            time.sleep(step0[1])
            return
        # hello
        opcode, payload = _stub_read_frame(conn)
        assert opcode == 0x1
        hello = json.loads(payload.decode())
        rec["hello"] = hello
        assert hello["box_id"] == self.box_id
        generation = hello["generation"]
        if step0[0] == "welcome-raw":
            _stub_send_json(conn, step0[1])
        else:
            _stub_send_json(conn, {"type": "welcome", "box_id": self.box_id,
                                   "accepted_generation": generation,
                                   "server_time": 1234567890})
        for step in script[1:]:
            kind = step[0]
            if kind == "send":
                _stub_send_json(conn, step[1])
            elif kind == "send-binary":
                _stub_send_frame(conn, step[1], opcode=0x2)
            elif kind == "send-masked":
                # A server MUST NOT mask: build a masked frame by hand.
                payload = step[1]
                mask = b"\x01\x02\x03\x04"
                masked = bytes(c ^ mask[i % 4]
                               for i, c in enumerate(payload))
                conn.sendall(bytes([0x81, 0x80 | len(payload)]) + mask
                             + masked)
            elif kind == "expect-pong":
                opcode, payload = _stub_read_frame(conn)
                frame = json.loads(payload.decode())
                assert frame["type"] == "pong", frame
                rec["frames"].append(frame)
            elif kind == "ping":
                _stub_send_json(conn, {"type": "ping",
                                       "generation": generation, "ts": 4242})
                deadline = time.time() + 5
                while True:
                    assert time.time() < deadline, \
                        "no pong arrived for the scripted ping"
                    opcode, payload = _stub_read_frame(conn)
                    frame = json.loads(payload.decode())
                    if frame.get("type") == "ping":
                        continue  # the client's own periodic ping; keep
                        # waiting for the pong that answers ours
                    assert frame["type"] == "pong" and \
                        frame["ts"] == 4242, frame
                    break
                rec["frames"].append(frame)
            elif kind == "send-ws-ping":
                _stub_send_frame(conn, step[1], opcode=0x9)
            elif kind == "expect-ws-pong":
                opcode, payload = _stub_read_frame(conn)
                assert opcode == 0xA and payload == step[1], \
                    (opcode, payload)
            elif kind == "drain":
                # Read client frames until the deadline, recording every
                # raw payload; JSON pings are never ponged (the point is
                # to observe, not to keepalive). Ends early if the client
                # goes away.
                deadline = time.time() + step[1]
                conn.settimeout(0.3)
                while time.time() < deadline:
                    try:
                        opcode, payload = _stub_read_frame(conn)
                    except socket.timeout:
                        continue
                    except (ConnectionError, OSError):
                        break
                    rec["frames_raw"].append(payload)
                conn.settimeout(10)
            elif kind == "send-command":
                _stub_send_json(conn, {"type": "command",
                                       "generation": generation,
                                       "seq": step[1], "epoch": step[2],
                                       "payload": step[3]})
            elif kind == "send-command-as":
                _stub_send_json(conn, {"type": "command",
                                       "generation": step[1],
                                       "seq": step[2], "epoch": step[3],
                                       "payload": step[4]})
            elif kind == "expect-acks":
                # Collect one command_ack per wanted seq, in order,
                # skipping the client's own periodic JSON pings. The
                # §3.1 shape (type/generation/seq, epoch when sent) is
                # asserted on every ack.
                want = list(step[1])
                acks = []
                deadline = time.time() + 10
                while len(acks) < len(want) and time.time() < deadline:
                    opcode, payload = _stub_read_frame(conn)
                    frame = json.loads(payload.decode())
                    if frame.get("type") == "ping":
                        continue  # the client's own keepalive ping
                    assert frame.get("type") == "command_ack", frame
                    assert frame.get("generation") == generation, frame
                    assert isinstance(frame.get("seq"), int) \
                        and not isinstance(frame.get("seq"), bool), frame
                    epoch = frame.get("epoch")
                    assert epoch is None or (
                        isinstance(epoch, int)
                        and not isinstance(epoch, bool)), frame
                    acks.append(frame)
                assert [a["seq"] for a in acks] == want, acks
                rec["frames"].extend(acks)
            elif kind == "close":
                code, extra = step[1], step[2] if len(step) > 2 else {}
                _stub_send_json(conn, {"type": "close", "generation":
                                       generation, "code": code, **extra})
                time.sleep(0.3)  # let the client read the close
                return
            elif kind == "close-tcp":
                return
            else:
                raise AssertionError(f"unknown stub step {kind}")
            # Drain any client pings that arrived meanwhile (auto-ponged
            # inside _stub_read_frame already).


def _run_client(ctx, stub):
    """Run cmd_phone_home against the stub; return its exit code.

    The daemon runs in a thread with a watchdog: every script drives the
    client to an exit (a close code), so a join timeout means the client
    wedged instead of exiting."""
    ctx.control = stub.url
    stub.start()
    stub._ready.wait(5)
    rc = []
    t = threading.Thread(target=lambda: rc.append(
        spark_pair.cmd_phone_home(ctx)), daemon=True)
    t.start()
    t.join(25)
    assert not t.is_alive(), "phone-home wedged instead of exiting"
    assert rc, "client thread died without a return code"
    return rc[0]


# -- framing unit tests ---------------------------------------------------------

class _FakeSock:
    """BytesIO-backed stand-in for a socket (recv only)."""
    def __init__(self, data):
        self._buf = io.BytesIO(data)

    def recv(self, n):
        return self._buf.read(n)


def _decode_raw(raw):
    return spark_pair._ws_decode_frame(spark_pair._WsReader(_FakeSock(raw)))


def test_frame_encode_is_masked():
    frame = spark_pair._ws_encode_frame(0x1, b"hello")
    assert frame[0] == 0x81  # FIN + text
    assert frame[1] & 0x80  # masked bit
    assert len(frame) == 2 + 4 + 5


def test_frame_decode_rejects_masked_server_frame():
    payload = b'{"type":"ping"}'
    mask = b"\x01\x02\x03\x04"
    masked = bytes(c ^ mask[i % 4] for i, c in enumerate(payload))
    raw = bytes([0x81, 0x80 | len(payload)]) + mask + masked
    with pytest.raises(spark_pair._WsProtocolError):
        _decode_raw(raw)


def test_frame_decode_rejects_oversize():
    raw = bytes([0x81, 0x7F]) + struct.pack(">Q", spark_pair._WS_MAX_FRAME + 1)
    with pytest.raises(spark_pair._WsProtocolError):
        _decode_raw(raw)


def test_frame_decode_roundtrip_unmasked():
    payload = b'{"type":"welcome"}'
    raw = bytes([0x81, len(payload)]) + payload
    opcode, out, fin = _decode_raw(raw)
    assert (opcode, out, fin) == (0x1, payload, True)


def test_backoff_schedule_bounds():
    d0 = spark_pair._ws_backoff_delay(0, rng=lambda: 0.0)
    d1 = spark_pair._ws_backoff_delay(0, rng=lambda: 1.0)
    assert d0 == pytest.approx(0.75)  # 1s - 25%
    assert d1 == pytest.approx(1.25)  # 1s + 25%
    # Doubling then the 60s cap (jitter applies before the final cap, so
    # the result never exceeds 60):
    assert spark_pair._ws_backoff_delay(1, rng=lambda: 0.0) == pytest.approx(1.5)
    assert spark_pair._ws_backoff_delay(10, rng=lambda: 1.0) == pytest.approx(60.0)
    # Jitter applies before the final cap: 64 * 0.75 = 48 < 60, no cap.
    assert spark_pair._ws_backoff_delay(10, rng=lambda: 0.0) == pytest.approx(48.0)


def test_close_action_table():
    A = spark_pair._phone_home_close_action
    assert A("revoked", {}) == ("exit", 1)
    assert A("expired", {}) == ("reconnect", 0)
    assert A("going-away", {})[0] == "reconnect"
    assert A("going-away", {})[1] >= 60
    assert A("superseded-generation", {}) == ("exit", 1)
    assert A("identity-mismatch", {}) == ("exit", 1)
    assert A("protocol-error", {}) == ("exit", 1)
    assert A("stale-generation", {"last_generation": 9}) == ("adopt", 10)
    assert A("stale-generation", {"last_generation": "9"}) == ("exit", 1)
    assert A("stale-generation", {}) == ("exit", 1)
    assert A("bogus-code", {}) == ("exit", 1)


def test_generation_claim_crash_safe(tmp_path):
    d = str(tmp_path)
    g1, s1 = spark_pair._phone_home_claim_generation(d)
    assert (g1, s1) == (1, "first-run")
    g2, s2 = spark_pair._phone_home_claim_generation(d)
    assert (g2, s2) == (2, "ok")  # never reuses
    # Corrupt file → counter-loss, restarts at 1 (the DO's
    # stale-generation fence is the recovery path).
    with open(os.path.join(d, "phone_home_generation.json"), "w") as f:
        f.write("garbage{")
    g3, s3 = spark_pair._phone_home_claim_generation(d)
    assert (g3, s3) == (1, "counter-loss")


def test_ws_url_derivation():
    assert spark_pair._ws_url_for_control("https://api.sparkvm.dev") == \
        "wss://api.sparkvm.dev"
    assert spark_pair._ws_url_for_control("http://127.0.0.1:8080/x") == \
        "ws://127.0.0.1:8080/x"
    # Non-loopback cleartext never reaches here: _resolve_control refuses
    # it first (fail-closed on the https/http spelling).
    ok, _ = spark_pair._check_control_url("http://example.com")
    assert not ok


# -- session behavior against the stub --------------------------------------------

def test_hello_welcome_generation_increments(ctx):
    stub = StubDO([[("welcome",), ("close", "revoked", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1  # revoked → exit, no reconnect
    assert len(stub.records) == 1
    assert stub.records[0]["hello"]["generation"] == 1
    assert stub.records[0]["hello"]["box_id"] == BOX_ID
    # Second run claims generation 2 — never reuses.
    stub2 = StubDO([[("welcome",), ("close", "revoked", {})]])
    rc = _run_client(ctx, stub2)
    assert rc == 1
    assert stub2.records[0]["hello"]["generation"] == 2


def test_revoked_no_reconnect_loop(ctx, capsys):
    stub = StubDO([[("welcome",), ("close", "revoked",
                                   {"reason": "token revoked"})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    assert len(stub.records) == 1  # exactly one connection: no reconnect
    err = capsys.readouterr()
    assert "re-pair" in err.err  # the human path, loud (via _fail → stderr)


def test_expired_reconnects_with_current_token(ctx):
    stub = StubDO([[("welcome",), ("close", "expired", {})],
                   [("welcome",), ("close", "revoked", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    assert len(stub.records) == 2
    # Same generation+1 on reconnect (plain reconnect bumps generation,
    # never epoch — asserted below).
    assert stub.records[1]["hello"]["generation"] == 2
    # The reconnect carries the current token.
    assert stub.records[1]["auth_header"] == f"Bearer {TOKEN}"
    # Server-directed reconnects back off with a floor (no zero-delay
    # hot loop); the interruptible sleep splits it into ≤1s quanta.
    assert 0.5 <= sum(ctx.sleeps) <= 1.5


def test_going_away_waits_sixty_seconds(ctx):
    stub = StubDO([[("welcome",), ("close", "going-away", {})],
                   [("welcome",), ("close", "revoked", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    assert len(stub.records) == 2
    # The ≥60 s wait is interruptible (1 s quanta), so the recorded total
    # is what matters, not any single sleep.
    assert sum(ctx.sleeps) >= 60, ctx.sleeps


def test_stale_generation_adopts_and_bumps_epoch(ctx):
    cursor = os.path.join(ctx.dir, "commands_cursor.json")
    with open(cursor, "w") as f:
        json.dump({"cursor": 41, "epoch": 3}, f)
    stub = StubDO([[("welcome",),
                    ("close", "stale-generation", {"last_generation": 9})],
                   [("welcome",), ("close", "revoked", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    assert len(stub.records) == 2
    # Adopted last_generation+1 verbatim (not +1 again on the claim path).
    assert stub.records[1]["hello"]["generation"] == 10
    with open(os.path.join(ctx.dir, "phone_home_generation.json")) as f:
        assert json.load(f)["generation"] == 10
    # Counter loss is a reboot-equivalent: epoch bumped, cursor kept.
    with open(cursor) as f:
        cur = json.load(f)
    assert cur == {"cursor": 41, "epoch": 4}


def test_plain_reconnect_leaves_epoch_alone(ctx):
    cursor = os.path.join(ctx.dir, "commands_cursor.json")
    with open(cursor, "w") as f:
        json.dump({"cursor": 41, "epoch": 3}, f)
    stub = StubDO([[("welcome",), ("close-tcp",)],
                   [("welcome",), ("close", "revoked", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    assert len(stub.records) == 2
    with open(cursor) as f:
        assert json.load(f) == {"cursor": 41, "epoch": 3}
    # Transport loss backs off (attempt 0 → ~0.75-1.25s total; the
    # interruptible sleep splits it into ≤1s quanta).
    assert 0.5 <= sum(ctx.sleeps) <= 1.5


def test_upgrade_401_rotates_once_then_reconnects(ctx, monkeypatch):
    calls = []

    def fake_rotate(ns):
        calls.append(1)
        with open(os.path.join(ctx.dir, "enrollment.json"), "w") as f:
            json.dump({"box_id": BOX_ID, "token": "tok-new",
                       "token_expires_at": int(time.time()) + 3600}, f)
        return 0

    monkeypatch.setattr(spark_pair, "cmd_rotate", fake_rotate)
    stub = StubDO([[("upgrade-401",)],
                   [("welcome",), ("close", "revoked", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    assert calls == [1]  # exactly one rotate attempt
    assert len(stub.records) == 2
    assert stub.records[1]["auth_header"] == "Bearer tok-new"


def test_upgrade_401_rotate_fails_means_repair(ctx, monkeypatch, capsys):
    monkeypatch.setattr(spark_pair, "cmd_rotate", lambda ns: 1)
    stub = StubDO([[("upgrade-401",)]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    assert len(stub.records) == 1  # no reconnect loop on 401


def test_upgrade_302_never_followed(ctx):
    stub = StubDO([[("upgrade-302",)],
                   [("welcome",), ("close", "revoked", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    # The client refused the redirect and backed off; the second
    # connection proves it never followed the Location to evil.test.
    assert len(stub.records) == 2
    for rec in stub.records:
        assert b"evil.test" not in rec["request"]


def test_upgrade_bad_accept_refused(ctx, capsys):
    stub = StubDO([[("upgrade-bad-accept",)],
                   [("welcome",), ("close", "revoked", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    assert len(stub.records) == 2  # retried with backoff after the refusal
    # The refusal must be the loud MITM warning — not a silent
    # transport-lost that a neutered (accept-anything) client also makes.
    err = capsys.readouterr()
    assert "Sec-WebSocket-Accept" in err.err


def test_ping_pong_keepalive(ctx):
    stub = StubDO([[("welcome",), ("ping",), ("close", "revoked", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    assert len(stub.records[0]["frames"]) == 1
    assert stub.records[0]["frames"][0]["ts"] == 4242


def test_client_sends_pings(ctx):
    got = []

    class PingStub(StubDO):
        def _serve(self, conn, script):
            # Like the base serve but records pings instead of scripted steps.
            rec = {"request": b"", "hello": None, "frames": [],
                   "auth_header": None, "upgrade_path": None}
            self.records.append(rec)
            head = self._read_http(conn)
            rec["request"] = head
            lines = head.decode("latin-1").split("\r\n")
            headers = {}
            for line in lines[1:]:
                if ":" in line:
                    k, v = line.split(":", 1)
                    headers[k.strip().lower()] = v.strip()
            rec["auth_header"] = headers.get("authorization")
            key = headers.get("sec-websocket-key", "")
            accept = base64.b64encode(
                hashlib.sha1((key + WS_GUID).encode()).digest()).decode()
            conn.sendall(("HTTP/1.1 101 Switching Protocols\r\n"
                          "Upgrade: websocket\r\n"
                          "Connection: Upgrade\r\n"
                          f"Sec-WebSocket-Accept: {accept}\r\n\r\n").encode())
            opcode, payload = _stub_read_frame(conn)
            hello = json.loads(payload.decode())
            rec["hello"] = hello
            _stub_send_json(conn, {"type": "welcome", "box_id": BOX_ID,
                                   "accepted_generation": hello["generation"],
                                   "server_time": 1})
            deadline = time.time() + 5
            while time.time() < deadline:
                opcode, payload = _stub_read_frame(conn)
                frame = json.loads(payload.decode())
                if frame.get("type") == "ping":
                    got.append(frame)
                    break
            _stub_send_json(conn, {"type": "close", "generation":
                                   hello["generation"], "code": "revoked"})
            time.sleep(0.3)

    stub = PingStub([[]])
    rc = _run_client(ctx, stub)
    assert rc == 1  # revoked close ends the run
    assert got, "client never sent its 30s-interval ping (patched to 0.2s)"
    assert got[0]["generation"] == 1


def test_credential_never_in_logs_or_frames(ctx, capsys):
    stub = StubDO([[("welcome",),
                    ("send", {"type": "ping", "generation": 1, "ts": 1}),
                    ("drain", 0.7),
                    ("close", "revoked",
                     {"reason": "token revoked; tok-secret-abc123 leaked?"})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    with open(os.path.join(ctx.dir, "phone_home.log"), "rb") as f:
        log = f.read()
    assert TOKEN.encode() not in log
    err = capsys.readouterr()
    assert TOKEN not in err.out and TOKEN not in err.err
    # The bearer travels only in the upgrade's Authorization header —
    # never in ANY frame on the wire (hello, pings, pongs: all recorded
    # raw during the drain).
    assert stub.records[0]["auth_header"] == f"Bearer {TOKEN}"
    assert stub.records[0]["frames_raw"], "drain recorded no client frames"
    assert TOKEN.encode() not in b"".join(stub.records[0]["frames_raw"])
    assert TOKEN.encode() not in json.dumps(
        stub.records[0]["hello"]).encode()


def test_heartbeat_untouched_by_phone_home(ctx):
    stub = StubDO([[("welcome",), ("close", "revoked", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    assert not os.path.exists(os.path.join(ctx.dir, "last_heartbeat.json"))


def test_superseded_generation_exits_loud(ctx, capsys):
    stub = StubDO([[("welcome",), ("close", "superseded-generation", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1  # fail closed: a concurrent session under our identity
    assert len(stub.records) == 1  # ... should not exist (we hold the lock)


def test_identity_mismatch_no_reconnect(ctx):
    stub = StubDO([[("welcome",), ("close", "identity-mismatch", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    assert len(stub.records) == 1


def test_masked_server_frame_is_protocol_error(ctx):
    stub = StubDO([[("welcome",),
                    ("send-masked", b'{"type":"ping","ts":1}'),
                    ("close", "revoked", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1  # protocol error → bug → no reconnect
    assert len(stub.records) == 1


def test_binary_frame_is_protocol_error(ctx):
    stub = StubDO([[("welcome",),
                    ("send-binary", b"\x00\x01"),
                    ("close", "revoked", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    assert len(stub.records) == 1


def test_second_instance_refuses_lock(ctx):
    import fcntl as _fcntl
    lock_path = os.path.join(ctx.dir, ".phone-home.lock")
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    _fcntl.flock(fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
    try:
        # Watchdog: a lock-check regression must fail, not hang the suite.
        rc = []
        t = threading.Thread(
            target=lambda: rc.append(spark_pair.cmd_phone_home(ctx)),
            daemon=True)
        t.start()
        t.join(10)
        assert not t.is_alive(), "second instance wedged instead of refusing"
        assert rc == [1]
    finally:
        _fcntl.flock(fd, _fcntl.LOCK_UN)
        os.close(fd)


# -- round-2 regression tests (adversarial review blockers) ----------------------

def test_welcome_timeout_reconnects_not_tracebacks(ctx):
    # Eng B1: a plane slow to send welcome (> read quantum) must read as
    # transport-lost → backoff reconnect, never a TimeoutError traceback.
    stub = StubDO([[("welcome-dwell", 2.0)],
                   [("welcome",), ("close", "revoked", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    assert len(stub.records) == 2


def test_send_oserror_maps_to_transport_lost():
    # Eng B2: a send-side EPIPE/RST is transport loss, not a traceback.
    class DeadSock:
        def sendall(self, b):
            raise OSError("broken pipe")

    s = spark_pair._PhoneHomeSession(None, DeadSock(), None, BOX_ID, 1,
                                     TOKEN)
    with pytest.raises(spark_pair._WsTransportLost):
        s.send({"type": "ping"})


def test_close_before_welcome_routes_through_close_table(ctx):
    # Eng B3: a spec-mandated stale-generation answering hello is not a
    # "bug" — the client must adopt, bump epoch, and reconnect.
    cursor = os.path.join(ctx.dir, "commands_cursor.json")
    with open(cursor, "w") as f:
        json.dump({"cursor": 41, "epoch": 3}, f)
    stub = StubDO([[("welcome-raw", {"type": "close", "generation": 1,
                                    "code": "stale-generation",
                                    "last_generation": 9})],
                   [("welcome",), ("close", "revoked", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    assert len(stub.records) == 2
    assert stub.records[1]["hello"]["generation"] == 10
    with open(cursor) as f:
        assert json.load(f)["epoch"] == 4


def test_rotate_budget_resets_after_healthy_session(ctx, monkeypatch):
    # Eng B4: one rotate per 401; a healthy welcome earns a fresh budget.
    calls = []

    def fake_rotate(ns):
        calls.append(1)
        with open(os.path.join(ctx.dir, "enrollment.json"), "w") as f:
            json.dump({"box_id": BOX_ID, "token": f"tok-new-{len(calls)}",
                       "token_expires_at": int(time.time()) + 3600}, f)
        return 0

    monkeypatch.setattr(spark_pair, "cmd_rotate", fake_rotate)
    stub = StubDO([[("upgrade-401",)],
                   [("welcome",), ("close-tcp",)],
                   [("upgrade-401",)],
                   [("welcome",), ("close", "revoked", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    assert calls == [1, 1]
    assert len(stub.records) == 4
    # records[2] is the second 401 (still on tok-new-1); records[3] is the
    # reconnect after the second rotate.
    assert stub.records[2]["auth_header"] == "Bearer tok-new-1"
    assert stub.records[3]["auth_header"] == "Bearer tok-new-2"


def test_expired_no_double_rotate(ctx, monkeypatch):
    # Eng B4: a plane closing expired in a loop must not spin
    # rotate → handshake → expired forever.
    with open(os.path.join(ctx.dir, "enrollment.json"), "w") as f:
        json.dump({"box_id": BOX_ID, "token": "tok-old",
                   "token_expires_at": int(time.time()) - 10}, f)
    calls = []

    def fake_rotate(ns):
        calls.append(1)
        with open(os.path.join(ctx.dir, "enrollment.json"), "w") as f:
            json.dump({"box_id": BOX_ID, "token": "tok-fresh",
                       "token_expires_at": int(time.time()) + 3600}, f)
        return 0

    monkeypatch.setattr(spark_pair, "cmd_rotate", fake_rotate)
    stub = StubDO([[("welcome",), ("close", "expired", {})],
                   [("welcome",), ("close", "expired", {})],
                   [("welcome",), ("close", "revoked", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    assert calls == [1]  # the second expired saw the live token: no rotate
    assert stub.records[1]["auth_header"] == "Bearer tok-fresh"
    assert stub.records[2]["auth_header"] == "Bearer tok-fresh"


def test_repeated_expired_backs_off_with_floor(ctx, monkeypatch):
    # Security B2: repeated server-directed closes must not become a
    # zero-delay hot reconnect loop. Scripted delays pin the growth:
    # first expired → 1.0s (1 quantum), second → 2.0s (2 quanta).
    delays = [1.0, 2.0]
    monkeypatch.setattr(spark_pair, "_ws_backoff_delay",
                        lambda attempt, rng=None: delays.pop(0))
    stub = StubDO([[("welcome",), ("close", "expired", {})],
                   [("welcome",), ("close", "expired", {})],
                   [("welcome",), ("close", "revoked", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    assert ctx.sleeps == [1.0, 1.0, 1.0]


def test_continuation_bomb_rejected():
    # Security B1 / Eng B5: the per-frame cap does not bound the
    # continuation count — the reassembled total is capped. The bomb is
    # *valid JSON* (a 1.5 MiB string) so only the total cap can catch it —
    # an undecodable payload would pass for the wrong reason.
    c1 = b'"' + b"x" * 524287
    c2 = b"x" * 524288
    c3 = b"x" * 524287 + b'"'

    def frag(first_opcode, chunk):
        return bytes([first_opcode, 127]) + struct.pack(">Q", len(chunk)) \
            + chunk

    raw = frag(0x01, c1) + frag(0x00, c2) + frag(0x80, c3)
    assert len(c1) + len(c2) + len(c3) > spark_pair._WS_MAX_FRAME
    with pytest.raises(spark_pair._WsProtocolError):
        spark_pair._ws_read_json_frame(spark_pair._WsReader(_FakeSock(raw)))


def test_fragmented_control_frame_rejected():
    with pytest.raises(spark_pair._WsProtocolError):
        _decode_raw(bytes([0x09, 5]) + b"hello")  # FIN=0 ping


def test_oversize_control_frame_rejected():
    # Wire spec §3.1: control-class frames MUST be ≤ 4 KB.
    obj = {"type": "ping", "generation": 1, "ts": 1, "pad": "x" * 5000}
    payload = json.dumps(obj).encode()
    raw = bytes([0x81, 127]) + struct.pack(">Q", len(payload)) + payload
    with pytest.raises(spark_pair._WsProtocolError):
        spark_pair._ws_read_json_frame(spark_pair._WsReader(_FakeSock(raw)))


def test_reserved_and_unknown_frames_ignored(ctx):
    # Malformed command frames (no shape to execute), a plane-sent
    # command_ack (box→DO only), and unknown frame types must not wedge
    # the channel. Well-formed command frames are EXECUTED now (S5b —
    # see the tests below); this one has an empty payload, so it is
    # still log-and-ignore.
    stub = StubDO([[("welcome",),
                    ("send", {"type": "command", "generation": 1, "seq": 7,
                              "epoch": 1, "payload": {}}),
                    ("send", {"type": "command_ack", "generation": 1,
                              "seq": 7, "epoch": 1}),
                    ("send", {"type": "mystery", "generation": 1}),
                    ("close", "revoked", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    assert len(stub.records) == 1  # channel survived to the close
    with open(os.path.join(ctx.dir, "phone_home.log")) as f:
        log = f.read()
    assert log.count("ignoring") >= 3


def test_pong_timeout_drops_dead_socket(ctx, monkeypatch):
    # QA B4: the §4 keepalive liveness property — no pong within the
    # timeout drops the socket and reconnects.
    monkeypatch.setattr(spark_pair, "_WS_PONG_TIMEOUT", 0.5)
    stub = StubDO([[("welcome",), ("drain", 3.0)],
                   [("welcome",), ("close", "revoked", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    assert len(stub.records) == 2


def test_ws_level_ping_pong(ctx):
    # QA B5: RFC 6455 pings get pong answers with the payload echoed.
    stub = StubDO([[("welcome",),
                    ("send-ws-ping", b"abc"),
                    ("expect-ws-pong", b"abc"),
                    ("close", "revoked", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1


def test_expired_no_live_token_rotates_once(ctx, monkeypatch):
    # QA B6: the expired → re-read → no-live-token → one-rotate branch.
    with open(os.path.join(ctx.dir, "enrollment.json"), "w") as f:
        json.dump({"box_id": BOX_ID, "token": "tok-old",
                   "token_expires_at": int(time.time()) - 10}, f)
    calls = []

    def fake_rotate(ns):
        calls.append(1)
        with open(os.path.join(ctx.dir, "enrollment.json"), "w") as f:
            json.dump({"box_id": BOX_ID, "token": "tok-fresh",
                       "token_expires_at": int(time.time()) + 3600}, f)
        return 0

    monkeypatch.setattr(spark_pair, "cmd_rotate", fake_rotate)
    stub = StubDO([[("welcome",), ("close", "expired", {})],
                   [("welcome",), ("close", "revoked", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    assert calls == [1]
    assert stub.records[1]["auth_header"] == "Bearer tok-fresh"


def test_bad_welcome_box_id_exits_no_reconnect(ctx):
    # QA B9: spec §2 identity binding — wrong box_id in welcome is fatal.
    stub = StubDO([[("welcome-raw", {"type": "welcome", "box_id": "WRONG",
                                    "accepted_generation": 1})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    assert len(stub.records) == 1


def test_bad_welcome_generation_exits_no_reconnect(ctx):
    stub = StubDO([[("welcome-raw", {"type": "welcome", "box_id": BOX_ID,
                                    "accepted_generation": 999})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    assert len(stub.records) == 1


def test_unknown_close_code_exits_no_reconnect(ctx):
    stub = StubDO([[("welcome",), ("close", "bogus-code", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    assert len(stub.records) == 1


# -- S5b: socket command frames + command_ack (issue #976) ------------------------
# The S5a harness above proved the connection core; these prove the
# command-carrying half against the same stub DO: command frames
# dispatch into the #874 ingest executor, acks ride the socket (§3.3
# decision — _http is monkeypatched to explode, so any HTTPS ack would
# fail the test), and untrusted frames are never executed.


def _s5b_setup(ctx, monkeypatch, tmp_path):
    """Ingest fixtures for socket-command tests.

    A tmp approvals dir (via SVM_APPROVALS_DIR), the Finding-50 owner
    lookup faked to swapd, the audit trail pointed at tmp, and _http
    rigged to explode — proving the socket path never touches the HTTPS
    ack endpoint. Returns the approvals dir."""
    approvals = tmp_path / "approvals"
    for sub in ("pending", "answered", "consumed"):
        (approvals / sub).mkdir(parents=True)
    monkeypatch.setenv("SVM_APPROVALS_DIR", str(approvals))
    monkeypatch.setattr(spark_pair, "_ingest_file_owner",
                        lambda path: "swapd")
    monkeypatch.setenv("CONFIRM_AUDIT", str(tmp_path / "audit.log"))

    def _no_http(method, url, body=None, headers=None):
        raise AssertionError(
            f"socket command path must not call _http: {method} {url}")
    monkeypatch.setattr(spark_pair, "_http", _no_http)
    return str(approvals)


_S5B_AID = "s5bcmd0000000001"


def _s5b_file_pending(approvals, aid=_S5B_AID):
    # No "requester" field: Finding-50 reads the requester from the
    # file's owner (faked to swapd above), never from the item.
    item = {"id": aid, "credential": "openai", "host": "api.openai.com",
            "method": "POST", "path_prefix": "/v1/chat",
            "scope": "", "job": "job-1", "kind": "grant-request",
            "created": "2026-10-04T00:00:00+00:00",
            "expires": "2099-01-01T00:00:00+00:00",
            "tenant_id": None}
    with open(os.path.join(approvals, "pending", aid + ".json"),
              "w") as f:
        json.dump(item, f)


def _s5b_decision(aid=_S5B_AID, decision="deny", dseq=1):
    # "deny" exercises the full stamp path without grant minting.
    return {"aid": aid, "decision": decision, "decision_seq": dseq,
            "idempotency_key":
                f"approval_decision:{BOX_ID}:{aid}:{dseq}"}


def _s5b_inner(decision=None):
    return {"kind": "approval_decision",
            "payload": decision if decision is not None
            else _s5b_decision()}


def _s5b_acks(stub):
    return [f for f in stub.records[0]["frames"]
            if f.get("type") == "command_ack"]


def _s5b_consumed(approvals, aid=_S5B_AID):
    p = os.path.join(approvals, "consumed", aid + ".json")
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return json.load(f)


def test_socket_command_delivery_stamps_and_socket_acks(ctx, monkeypatch,
                                                       tmp_path):
    approvals = _s5b_setup(ctx, monkeypatch, tmp_path)
    _s5b_file_pending(approvals)
    stub = StubDO([[("welcome",),
                    ("send-command", 1, 0, _s5b_inner()),
                    ("expect-acks", [1]),
                    ("close", "revoked", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    acks = _s5b_acks(stub)
    assert len(acks) == 1
    ack = acks[0]
    assert ack["seq"] == 1
    assert ack["epoch"] == 0  # the frame's epoch echoed back
    assert ack["generation"] == stub.records[0]["hello"]["generation"]
    # The decision went through the #874 executor: the consumed record
    # carries the plane receipt fields.
    stamped = _s5b_consumed(approvals)
    assert stamped is not None, "decision was never stamped"
    assert stamped["decision"] == "deny"
    assert stamped["decision_origin"] == "plane"
    assert stamped["plane_seq"] == 1
    # _http exploding proves the ack rode the socket, never HTTPS.


def test_socket_command_redelivery_deduped(ctx, monkeypatch, tmp_path):
    approvals = _s5b_setup(ctx, monkeypatch, tmp_path)
    _s5b_file_pending(approvals)
    stub = StubDO([[("welcome",),
                    ("send-command", 1, 0, _s5b_inner()),
                    ("send-command", 1, 0, _s5b_inner()),
                    ("expect-acks", [1, 1]),
                    ("close", "revoked", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    # One stamp, one idempotency-log entry, two idempotent acks: the
    # re-execution was deduped, the lost-ack heal still works.
    assert _s5b_consumed(approvals)["plane_seq"] == 1
    with open(os.path.join(ctx.dir, "ingested_decisions.json")) as f:
        assert len(json.load(f)) == 1


def test_socket_command_gap_holds_prefix(ctx, monkeypatch, tmp_path):
    # The contiguous-ack guard: seq 3 must not be acked (or stamped)
    # until the missing seq 2 arrives — the DO's re-drive heals the gap.
    approvals = _s5b_setup(ctx, monkeypatch, tmp_path)
    aids = {1: "s5bgap0000000001", 2: "s5bgap0000000002",
            3: "s5bgap0000000003"}
    for seq, aid in aids.items():
        _s5b_file_pending(approvals, aid)

    def inner(seq, aid):
        return _s5b_inner(_s5b_decision(aid=aid, dseq=seq))

    stub = StubDO([[("welcome",),
                    ("send-command", 1, 0, inner(1, aids[1])),
                    ("send-command", 3, 0, inner(3, aids[3])),  # gap
                    ("send-command", 2, 0, inner(2, aids[2])),
                    ("send-command", 3, 0, inner(3, aids[3])),  # re-drive
                    ("expect-acks", [1, 2, 3]),
                    ("close", "revoked", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    for aid in aids.values():
        assert _s5b_consumed(approvals, aid) is not None, \
            f"aid {aid} was never stamped"


def test_socket_command_malformed_frame_no_ack(ctx, monkeypatch, tmp_path,
                                              capsys):
    _s5b_setup(ctx, monkeypatch, tmp_path)
    stub = StubDO([[("welcome",),
                    ("send-command", "bogus", 0, _s5b_inner()),
                    ("close", "revoked", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    assert _s5b_acks(stub) == []
    assert "malformed command frame" in capsys.readouterr().out


_S5B_AID2 = "s5bcmd0000000002"


def test_socket_command_wrong_generation_ignored(ctx, monkeypatch,
                                                tmp_path):
    # A command fenced to another generation is never executed and never
    # acked — the fence holds on the socket path exactly as on upgrade.
    # The valid first command proves the handler is live, so this is not
    # the old log-and-ignore-everything behavior.
    approvals = _s5b_setup(ctx, monkeypatch, tmp_path)
    _s5b_file_pending(approvals, _S5B_AID)
    _s5b_file_pending(approvals, _S5B_AID2)
    stub = StubDO([[("welcome",),
                    ("send-command", 1, 0, _s5b_inner(
                        _s5b_decision(aid=_S5B_AID, dseq=1))),
                    ("send-command-as", 999, 2, 0, _s5b_inner(
                        _s5b_decision(aid=_S5B_AID2, dseq=2))),
                    ("expect-acks", [1]),
                    ("close", "revoked", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    assert [a["seq"] for a in _s5b_acks(stub)] == [1]
    assert _s5b_consumed(approvals, _S5B_AID) is not None
    assert _s5b_consumed(approvals, _S5B_AID2) is None


def test_socket_command_unknown_kind_acked_not_executed(ctx, monkeypatch,
                                                       tmp_path):
    # Ack-and-log: one unknown kind must not wedge the queue.
    approvals = _s5b_setup(ctx, monkeypatch, tmp_path)
    stub = StubDO([[("welcome",),
                    ("send-command", 1, 0,
                     {"kind": "future_kind", "payload": {}}),
                    ("expect-acks", [1]),
                    ("close", "revoked", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    assert os.listdir(os.path.join(approvals, "consumed")) == []


def test_socket_command_oversize_payload_rejected(ctx, monkeypatch,
                                                 tmp_path, capsys):
    # Wire-spec §3.3: command payloads are ≤ 16 KiB. A bigger payload is
    # a plane bug — rejected, never executed, never acked.
    _s5b_setup(ctx, monkeypatch, tmp_path)
    big = {"kind": "approval_decision",
           "payload": {"pad": "x" * (20 * 1024)}}
    stub = StubDO([[("welcome",),
                    ("send-command", 1, 0, big),
                    ("close", "revoked", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    assert _s5b_acks(stub) == []
    assert "16 KiB" in capsys.readouterr().out


def test_received_command_ack_ignored(ctx, monkeypatch, tmp_path):
    # command_ack is box→DO only (§3.1): a DO sending one is a plane bug —
    # logged, never acted on, never fatal to the daemon. The valid
    # command first proves the channel is live (not the old
    # ignore-everything behavior).
    approvals = _s5b_setup(ctx, monkeypatch, tmp_path)
    _s5b_file_pending(approvals)
    stub = StubDO([[("welcome",),
                    ("send-command", 1, 0, _s5b_inner()),
                    ("send", {"type": "command_ack", "generation": 1,
                              "seq": 7, "epoch": 0}),
                    ("expect-acks", [1]),
                    ("close", "revoked", {})]])
    rc = _run_client(ctx, stub)
    assert rc == 1
    assert [a["seq"] for a in _s5b_acks(stub)] == [1]
    assert len(stub.records) == 1  # channel survived to the close
