#!/usr/bin/env python3
"""Relay dial prober — R2a active instrument (GitHub #1414).

The active half of the relay-liveness lane (`docs/RELAY_LIVENESS_DESIGN.md`
§3, §8 R2a; gap analysis `docs/RELAY_LIVENESS_REMAINING_BUILDS_GAP_ANALYSIS.md`
F-RL2-1/D-RL2-1). Channel A (`hosted/relay_liveness.py`, R1) journals tenant
sessions passively; this module is channel B: the control plane dials the
tenant's path exactly as the tenant would — resolve relay host → TCP to the
relay listener → SSH transport handshake through the splice to the box's
private provider leg → verify the host key against the pinned fingerprint →
close cleanly **before authentication**.

Handshake-only, by construction (design §7, §9 Q4):

- The prober holds no tenant credential and no private key material. It
  never sends SSH_MSG_NEWKEYS (21) or any SSH_MSG_USERAUTH_* (50–79) packet;
  the session ends with SSH_MSG_DISCONNECT (1) after the host-key blob is
  read from the server's KEX_DH_GEX_REPLY. "Handshake-only" is provable:
  the test suite asserts the exact message-number transcript.
- The pinned fingerprint arrives as a call parameter — it is the session's
  connection-bundle value (`harness/provider_iface.py::SshInfo`), re-pinned
  on session restart per endpoint rule 7 / design §9 Q5 / D-RL2-3. This
  module never persists a fingerprint, never caches one, and a prober
  "config" that names a fingerprint is a review rejection.
- Key exchange is diffie-hellman-group-exchange-sha256 (RFC 4419): the
  server supplies the group, so the prober hardcodes no DH parameters. The
  group parameters are never validated or used beyond the message flow —
  the prober computes no shared secret and derives no keys; the only value
  extracted from the handshake is the server's host-key blob, whose
  SHA256 fingerprint is compared against the pin. A server that does not
  offer group-exchange-sha256 in its KEXINIT is a handshake the prober
  cannot complete (box_leg_defect, "kex_mismatch").

Outcome taxonomy (design §3, verbatim — the module emits these strings
exactly; R2b maps them to the §5 `relay_path_state` vocabulary):

- ``path_ok`` — full path works, host key verified.
- ``relay_defect`` — the relay listener itself not responding (TCP
  connect refused/timed out, or the relay host unresolvable).
- ``cert_defect`` — handshake completed but host-key verification failed.
- ``box_leg_defect`` — relay answers TCP but the private leg fails
  (no/bad SSH banner, handshake stalls or breaks, KEX mismatch).
- ``provider_not_running`` — provider state is not RUNNING; the prober
  stands down without dialing (provider state is the authority per
  endpoint §4 AND-combine; design §3). D-RL2-4: reads the H4
  ``ProviderState`` contract via a caller-supplied callable; #905's
  driver is pending, so acceptance uses a fake driver.

Identity-marker discriminator (design §2): the prober's client
identification string is ``SSH-2.0-sparkvm-relay-prober``. The relay
daemon marks journal frames from sessions carrying this ident with
``prober=True``; ``hosted/relay_liveness.py::emit_frame`` drops them, so
a probe never evidences itself in channel A. The marker shape is covered
by this module's tests per relay_liveness's docstring.

§4 no-inbound discipline: the prober dials *outbound* from the control
plane to the relay's tenant-facing listener — the same listener tenants
use — and traverses no path a tenant couldn't use. It opens no inbound
path to the VM (`public_ingress: false` untouched).

Stdlib only, like relay_liveness.py — this module must run unchanged on
the control plane without extra dependencies.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import os
import re
import socket
import struct
import time
from collections import namedtuple

# ---------------------------------------------------------------------------
# §3 outcome taxonomy (verbatim strings)
# ---------------------------------------------------------------------------

PATH_OK = "path_ok"
RELAY_DEFECT = "relay_defect"
CERT_DEFECT = "cert_defect"
BOX_LEG_DEFECT = "box_leg_defect"
PROVIDER_NOT_RUNNING = "provider_not_running"

OUTCOMES = frozenset(
    {
        PATH_OK,
        RELAY_DEFECT,
        CERT_DEFECT,
        BOX_LEG_DEFECT,
        PROVIDER_NOT_RUNNING,
    }
)

# R2's identity-marker discriminator (design §2). The relay daemon marks
# journal frames whose session carried this client ident with prober=True;
# relay_liveness.emit_frame drops those frames.
PROBER_IDENT = "SSH-2.0-sparkvm-relay-prober"

# The pinned fingerprint is the connection bundle's OpenSSH form
# (``ssh-keygen -l -E sha256``): "SHA256:" + unpadded base64. Anything
# else is rejected fail-closed before any network happens.
_FINGERPRINT_RE = re.compile(r"^SHA256:[A-Za-z0-9+/]+={0,2}$")

# SSH wire constants (RFC 4253 / RFC 4419).
_SSH_MSG_DISCONNECT = 1
_SSH_MSG_KEXINIT = 20
_SSH_MSG_NEWKEYS = 21
_SSH_MSG_KEX_DH_GEX_REQUEST = 34
_SSH_MSG_KEX_DH_GEX_GROUP = 31
_SSH_MSG_KEX_DH_GEX_INIT = 32
_SSH_MSG_KEX_DH_GEX_REPLY = 33
_SSH_MSG_USERAUTH_REQUEST = 50

_KEX_ALGO = b"diffie-hellman-group-exchange-sha256"

_MAX_PACKET_LEN = 35000  # sanity bound on one SSH binary packet
_MAX_BANNER_LINE = 512  # banner lines longer than this are hostile
_MAX_PRE_BANNER_LINES = 5  # RFC 4253 §4.2 tolerance for pre-version lines

ProbeResult = namedtuple("ProbeResult", ["outcome", "detail"])
# outcome ∈ OUTCOMES. detail always carries vm_id, elapsed_ms,
# prober_ident. provider_not_running adds provider_state + dialed=False;
# defects add "error" (and server_banner once a banner was read);
# path_ok/cert_defect add server_banner, observed_fingerprint,
# host_key_algo.


class _ProbeError(Exception):
    """Handshake failure that maps to an outcome (not a caller bug)."""


def _require_key_material(name, value):
    if not isinstance(value, str) or not value:
        raise ValueError("%s must be a non-empty str" % name)
    if "\x00" in value:
        raise ValueError("%s must not contain U+0000" % name)


def _normalize_fingerprint(pinned):
    """Fail-closed pinned-fingerprint check. Returns the digest bytes."""
    _require_key_material("pinned_fingerprint", pinned)
    if not _FINGERPRINT_RE.match(pinned):
        raise ValueError(
            "pinned_fingerprint must be OpenSSH SHA256 form "
            "'SHA256:<base64>', got %r" % (pinned[:32],)
        )
    b64 = pinned[len("SHA256:"):]
    try:
        digest = base64.b64decode(b64 + "=" * (-len(b64) % 4))
    except (binascii.Error, ValueError):
        raise ValueError("pinned_fingerprint is not valid base64")
    if len(digest) != 32:
        raise ValueError(
            "pinned_fingerprint must decode to 32 bytes (SHA-256)"
        )
    return digest


def _fingerprint_of(host_key_blob):
    """OpenSSH SHA256 fingerprint of a raw host-key blob."""
    return "SHA256:" + base64.b64encode(
        hashlib.sha256(host_key_blob).digest()
    ).decode("ascii").rstrip("=")


def _sanitize_banner(raw):
    """Operator-surface banner: ASCII-printable only, bounded length."""
    text = raw.decode("ascii", errors="replace")
    text = "".join(c for c in text if 32 <= ord(c) < 127)
    return text[:80]


# ---------------------------------------------------------------------------
# SSH binary-packet layer (RFC 4253 §6; pre-NEWKEYS, so no MAC)
# ---------------------------------------------------------------------------


def _mpint(n):
    """Encode an int as an SSH mpint."""
    if n < 0:
        raise ValueError("mpint must be non-negative")
    raw = n.to_bytes((n.bit_length() + 7) // 8 or 1, "big")
    if raw[0] & 0x80:
        raw = b"\x00" + raw
    return struct.pack(">I", len(raw)) + raw


def _string(b):
    return struct.pack(">I", len(b)) + b


def _name_list(names):
    return _string(b",".join(names))


def _build_packet(payload):
    pad_len = 8 - ((5 + len(payload)) % 8)
    if pad_len < 4:
        pad_len += 8
    packet_len = 1 + len(payload) + pad_len
    return (
        struct.pack(">I", packet_len)
        + struct.pack("B", pad_len)
        + payload
        + os.urandom(pad_len)
    )


class _Reader:
    def __init__(self, sock, io_timeout_s, deadline):
        self._sock = sock
        self._io_timeout_s = io_timeout_s
        # Absolute deadline for the whole probe: a trickling server must
        # not stretch the call one per-recv timeout at a time.
        self._deadline = deadline
        self.buf = b""

    def _recv(self, n):
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise _ProbeError("io_deadline")
        # This recv returns no later than the deadline: min() caps the
        # block at the time left, so the probe cannot overrun it.
        self._sock.settimeout(min(self._io_timeout_s, remaining))
        try:
            chunk = self._sock.recv(n)
        except socket.timeout:
            # The shrinking timeout above fires at the deadline edge, so
            # a timeout here means the bound stopped us: report one
            # token for the bound, not two. (0.1s grace for early-firing
            # timeouts under scheduling jitter.)
            if self._deadline - time.monotonic() <= 0.1:
                raise _ProbeError("io_deadline")
            raise
        if not chunk:
            raise _ProbeError("eof")
        return chunk

    def _recv_exact(self, n):
        while len(self.buf) < n:
            self.buf += self._recv(n - len(self.buf))
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def read_line(self):
        """One \\n-terminated line, bounded."""
        while b"\n" not in self.buf:
            if len(self.buf) > _MAX_BANNER_LINE:
                raise _ProbeError("banner_line_too_long")
            self.buf += self._recv(256)
        line, self.buf = self.buf.split(b"\n", 1)
        if len(line) > _MAX_BANNER_LINE:
            raise _ProbeError("banner_line_too_long")
        return line

    def read_packet(self):
        """One SSH binary packet → payload bytes."""
        packet_len = struct.unpack(">I", self._recv_exact(4))[0]
        if packet_len > _MAX_PACKET_LEN or packet_len < 12:
            raise _ProbeError("bad_packet_length")
        body = self._recv_exact(packet_len)
        pad_len = body[0]
        if pad_len < 4 or pad_len >= packet_len:
            raise _ProbeError("bad_padding")
        return body[1 : packet_len - pad_len]


def _build_kexinit():
    cookie = os.urandom(16)
    payload = (
        struct.pack("B", _SSH_MSG_KEXINIT)
        + cookie
        + _name_list([_KEX_ALGO])
        + _name_list([b"ssh-rsa", b"rsa-sha2-256", b"ssh-ed25519"])
        + _name_list([b"aes128-ctr"])
        + _name_list([b"aes128-ctr"])
        + _name_list([b"hmac-sha2-256"])
        + _name_list([b"hmac-sha2-256"])
        + _name_list([b"none"])
        + _name_list([b"none"])
        + _name_list([b""])
        + _name_list([b""])
        + struct.pack("B", 0)  # first_kex_packet_follows = FALSE
        + struct.pack(">I", 0)  # reserved
    )
    return _build_packet(payload)


def _parse_server_kexinit(payload):
    """Returns the server's kex name-list (bytes). Raises _ProbeError."""
    if not payload or payload[0] != _SSH_MSG_KEXINIT:
        raise _ProbeError("unexpected_msg_%d" % (payload[0] if payload else -1))
    off = 1 + 16
    lists = []
    for _ in range(10):
        if off + 4 > len(payload):
            raise _ProbeError("truncated_kexinit")
        (ln,) = struct.unpack(">I", payload[off : off + 4])
        off += 4
        if off + ln > len(payload):
            raise _ProbeError("truncated_kexinit")
        lists.append(payload[off : off + ln])
        off += ln
    return lists[0]


def _parse_mpint(buf, off):
    if off + 4 > len(buf):
        raise _ProbeError("truncated_mpint")
    (ln,) = struct.unpack(">I", buf[off : off + 4])
    off += 4
    if off + ln > len(buf):
        raise _ProbeError("truncated_mpint")
    return int.from_bytes(buf[off : off + ln], "big"), off + ln


def _parse_string(buf, off):
    if off + 4 > len(buf):
        raise _ProbeError("truncated_string")
    (ln,) = struct.unpack(">I", buf[off : off + 4])
    off += 4
    if off + ln > len(buf):
        raise _ProbeError("truncated_string")
    return buf[off : off + ln], off + ln


# ---------------------------------------------------------------------------
# The probe
# ---------------------------------------------------------------------------


def _detail(vm_id, start, **extra):
    d = {
        "vm_id": vm_id,
        "elapsed_ms": int((time.monotonic() - start) * 1000),
        "prober_ident": PROBER_IDENT,
    }
    d.update(extra)
    return d


def probe(
    vm_id,
    *,
    relay_host,
    relay_port,
    pinned_fingerprint,
    provider_state_fn,
    connect_timeout_s=5.0,
    io_timeout_s=10.0,
):
    """Dial the tenant's relay path handshake-only; return a ProbeResult.

    ``provider_state_fn`` is a zero-arg callable returning the H4
    ``ProviderState`` value name (e.g. ``"running"``) for this vm_id; the
    fake driver stands in until #905 ships (D-RL2-4). The prober dials
    only when the state is exactly ``"running"`` — any other state (or
    any unrecognized value) stands down as ``provider_not_running``
    without touching the network. A raising provider_state_fn is a
    caller bug and propagates.

    ``pinned_fingerprint`` is the session's connection-bundle fingerprint
    (OpenSSH ``SHA256:<base64>`` form); validated before any network.

    ``detail`` keys per outcome (R2b consumer contract): every result
    carries ``vm_id``, ``elapsed_ms``, ``prober_ident``;
    ``provider_not_running`` adds ``provider_state`` + ``dialed=False``;
    defects add ``error`` (and ``server_banner`` once a banner was read);
    ``path_ok``/``cert_defect`` add ``server_banner``,
    ``observed_fingerprint``, ``host_key_algo``.

    Raise contract: ``ValueError`` on bad arguments (before any network);
    a raising ``provider_state_fn`` propagates as a caller bug. Callers
    (R2b) must wrap the call if the driver can fail.

    Teardown contract: once the host key is read and the outcome decided,
    the closing DISCONNECT is best-effort — a post-handshake I/O failure
    (e.g. the peer RSTs after the reply) never changes the outcome.
    """
    start = time.monotonic()
    _require_key_material("vm_id", vm_id)
    _require_key_material("relay_host", relay_host)
    if not isinstance(relay_port, int) or not 1 <= relay_port <= 65535:
        raise ValueError("relay_port must be an int in 1..65535")
    if connect_timeout_s <= 0 or io_timeout_s <= 0:
        raise ValueError("connect_timeout_s and io_timeout_s must be positive")
    pin_digest = _normalize_fingerprint(pinned_fingerprint)

    state = provider_state_fn()
    if not isinstance(state, str) or not state:
        raise ValueError("provider_state_fn must return a non-empty str")
    if state != "running":
        # D-RL2-4 / design §3: provider state is the authority. Stand
        # down without dialing — probing a suspended/waking/provisioning
        # box is not a liveness question, and the prober must never wake
        # or otherwise change provider state.
        return ProbeResult(
            PROVIDER_NOT_RUNNING,
            _detail(vm_id, start, provider_state=state, dialed=False),
        )

    # Absolute I/O deadline for the whole probe: the per-recv socket
    # timeout alone lets a trickling server stretch the call one timeout
    # at a time. _dial enforces this on every recv.
    deadline = start + connect_timeout_s + io_timeout_s

    try:
        return _dial(
            vm_id,
            relay_host,
            relay_port,
            pin_digest,
            start,
            deadline,
            connect_timeout_s=connect_timeout_s,
            io_timeout_s=io_timeout_s,
        )
    except _ProbeError as e:
        return ProbeResult(
            BOX_LEG_DEFECT,
            _detail(
                vm_id,
                start,
                server_banner=_sanitize_banner(
                    getattr(e, "banner", "").encode("ascii", "replace")
                ),
                error=str(e),
            ),
        )
    except (socket.gaierror, ConnectionRefusedError, TimeoutError,
            OSError) as e:
        # The listener itself is not responding (or the relay host does
        # not resolve): the relay path is defective, per §3.
        return ProbeResult(
            RELAY_DEFECT,
            _detail(vm_id, start, error="%s: %s"
                    % (type(e).__name__, str(e)[:120])),
        )


def _dial(
    vm_id,
    relay_host,
    relay_port,
    pin_digest,
    start,
    deadline,
    connect_timeout_s,
    io_timeout_s,
):
    banner = ""
    # Connect phase: failures here mean the relay listener itself is not
    # responding (refused/timed out/unresolvable) -> relay_defect, mapped
    # by probe(). Everything after a successful connect is the box leg:
    # the listener answered, so later failures are box_leg_defect.
    sock = socket.create_connection(
        (relay_host, relay_port), timeout=connect_timeout_s
    )
    try:
        reader = _Reader(sock, io_timeout_s, deadline)

        # --- version exchange (RFC 4253 §4.2) ---
        non_ssh_lines = 0
        for _ in range(_MAX_PRE_BANNER_LINES + 1):
            try:
                line = reader.read_line()
            except _ProbeError as e:
                if non_ssh_lines:
                    # The server spoke, but no SSH banner arrived before
                    # the stream broke: attribute the break to the banner
                    # ("eof" alone would mislead the operator).
                    raise _ProbeError(
                        "no_ssh_banner_after_%d_non_ssh_lines"
                        % non_ssh_lines
                    )
                raise
            if line.startswith(b"SSH-"):
                banner = line.decode("ascii", errors="replace")
                break
            non_ssh_lines += 1
        else:
            raise _ProbeError("no_ssh_banner")
        if not banner.startswith("SSH-2.0-"):
            raise _ProbeError("banner_not_ssh2")
        sock.sendall(PROBER_IDENT.encode("ascii") + b"\r\n")

        # --- KEXINIT ---
        sock.sendall(_build_kexinit())
        server_kex = _parse_server_kexinit(reader.read_packet())
        if _KEX_ALGO not in server_kex.split(b","):
            raise _ProbeError("kex_mismatch")

        # --- group exchange (RFC 4419): the server supplies p, g ---
        gex_request = struct.pack("B", _SSH_MSG_KEX_DH_GEX_REQUEST)
        gex_request += struct.pack(">III", 2048, 2048, 2048)
        sock.sendall(_build_packet(gex_request))
        group_payload = reader.read_packet()
        if not group_payload or group_payload[0] != _SSH_MSG_KEX_DH_GEX_GROUP:
            raise _ProbeError(
                "unexpected_msg_%d" % (group_payload[0] if group_payload else -1)
            )
        p, off = _parse_mpint(group_payload, 1)
        g, off = _parse_mpint(group_payload, off)
        if p < 3 or g < 2 or g >= p:
            raise _ProbeError("bad_dh_group")

        x = int.from_bytes(os.urandom(32), "big") % (p - 1)
        if x < 2:
            x = 2
        e = pow(g, x, p)
        sock.sendall(
            _build_packet(struct.pack("B", _SSH_MSG_KEX_DH_GEX_INIT) + _mpint(e))
        )
        reply = reader.read_packet()
        if not reply or reply[0] != _SSH_MSG_KEX_DH_GEX_REPLY:
            raise _ProbeError(
                "unexpected_msg_%d" % (reply[0] if reply else -1)
            )
        host_key_blob, off = _parse_string(reply, 1)
        # f is parsed for shape only (the signature is never read) — the
        # prober never completes the exchange, so neither is ever used.
        _parse_mpint(reply, off)

        observed = _fingerprint_of(host_key_blob)
        outcome = (
            PATH_OK
            if hmac.compare_digest(
                hashlib.sha256(host_key_blob).digest(), pin_digest
            )
            else CERT_DEFECT
        )

        # The handshake is complete here: the outcome is decided from the
        # verified host key, and nothing after this point can change it. A
        # peer that RSTs the connection after the host-key reply must not
        # demote a path_ok/cert_defect to box_leg_defect — the §3 taxonomy
        # describes the handshake, and the handshake is done.
        result = ProbeResult(
            outcome,
            _detail(
                vm_id,
                start,
                server_banner=_sanitize_banner(banner.encode("ascii", "replace")),
                observed_fingerprint=observed,
                host_key_algo=_host_key_algo(host_key_blob),
            ),
        )

        # --- close cleanly before authentication: DISCONNECT, then TCP ---
        # Best-effort only: the outcome above is already decided, so a
        # teardown I/O failure must not re-enter the error classification.
        disc = struct.pack("B", _SSH_MSG_DISCONNECT)
        disc += struct.pack(">I", 11)  # SSH_DISCONNECT_BY_APPLICATION
        disc += _string(b"probe complete")
        disc += _string(b"")
        try:
            sock.sendall(_build_packet(disc))
        except OSError:
            pass
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass

        return result
    except _ProbeError as e:
        e.banner = banner
        raise
    except OSError as e:
        # Post-connect I/O failure (timeout, reset, refused mid-
        # handshake): the listener answered TCP, so this is the box leg
        # failing — never relay_defect.
        err = _ProbeError(
            "handshake_io_%s_%s" % (type(e).__name__, str(e)[:80])
        )
        err.banner = banner
        raise err
    finally:
        try:
            sock.close()
        except OSError:
            pass


def _host_key_algo(host_key_blob):
    """The key-type name from the blob's leading string (operator surface)."""
    try:
        name, _ = _parse_string(host_key_blob, 0)
        return _sanitize_banner(name)
    except _ProbeError:
        return "unknown"
